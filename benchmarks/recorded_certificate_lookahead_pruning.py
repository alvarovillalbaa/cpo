"""Skip a fallback read when spending it leaves no funded alternate certificate."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_certificate_lookahead as baseline
from cpo._contract import digest


REFERENCE = 'docs/recorded-certificate-lookahead-results-v1.json'
REFERENCE_SHA256 = '15560d69c8b168af50a31f561fa6e787eff107f78bc89c61ef9bef525912b8b6'
original_search = baseline.search_for_stronger


class FirstNomineeSettled(Exception):
    """The next scheduled fallback read cannot lead to a different selection."""


def later_can_qualify(incumbent, later, rows, training, ledger, *, target, protected, deadline, cap):
    """Check best-case funding after one additional read of the first candidate."""
    for prompt in later:
        evidence = {row.id: ledger[prompt, row.id].passed for row in rows if (prompt, row.id) in ledger}
        if any(evidence.get(case) is False for case in protected):
            continue
        needed = max(target - sum(evidence.values()), len(protected - evidence.keys()))
        if needed == 0:
            return True
        reserve = sum((name, row.id) not in ledger for name in (incumbent, prompt) for row in training)
        available = min(deadline, cap - reserve) - len(ledger) - 1
        if needed <= min(available, len(rows) - len(evidence)):
            return True
    return False


def prune(incumbent, first, roster, rows, training, observe, ledger, *, cap, extra):
    base = {row.id: ledger[incumbent, row.id].passed for row in rows}
    target = sum(base.values()) + 2
    protected = {row.id for row in rows if row.critical and base[row.id]}
    deadline = len(ledger) + extra
    later = roster[roster.index(first) + 1:]

    def evaluate(prompt, row):
        if prompt == first and not later_can_qualify(incumbent, later, rows, training, ledger, target=target,
                                                     protected=protected, deadline=deadline, cap=cap):
            raise FirstNomineeSettled
        return observe(prompt, row)

    try:
        return original_search(incumbent, first, roster, rows, training, evaluate, ledger, cap=cap, extra=extra)
    except FirstNomineeSettled:
        return first, False


def prepare():
    parent, math_data, transfer_data = baseline.prepare()
    reference = baseline.read_reference(REFERENCE, REFERENCE_SHA256, parent)
    plan = {'protocol': 'recorded-certificate-lookahead-pruning-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256, 'gepaVersion': parent['gepaVersion'],
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Keep the original validation allowances and scheduled reads. Stop before a read of the '
                     'fallback if buying it leaves no way for a later candidate to certify the target and keep '
                     'its full training reserve. Replay each original and pruned nomination, deployment, and '
                     'held-out decision.'}
    return plan, parent, math_data, transfer_data, reference


def execute(plan, parent, math_data, transfer_data, reference):
    original_trial = baseline.trial

    def trial(*arguments):
        old, old_trace, old_grades = original_trial(*arguments)
        with patch.object(baseline, 'search_for_stronger', prune):
            point, trace, grades = original_trial(*arguments)
        if trace[:4] != old_trace[:4] or grades != old_grades:
            raise ValueError('Skipping a fallback read changed the nominee, deployment, or held-out grade')
        old_reads = old.get('extraValidationLookups', 0)
        new_reads = point.get('extraValidationLookups', 0)
        if new_reads > old_reads or point['searchLookups'] > old['searchLookups']:
            raise ValueError('An exact pruning rule added a paid search read')
        return {**point, 'pairedDecisionsChecked': 1, 'baselinePaidLookups': old['paidLookups'],
                'baselineExtraValidationLookups': old_reads, 'validationLookupsSaved': old_reads - new_reads,
                'qualificationLookupDelta': point['qualificationLookups'] - old['qualificationLookups']}, trace, grades

    with patch.object(baseline, 'trial', trial):
        report = baseline.replay(parent, math_data, transfer_data)

    def selected(result, old):
        output = {}
        for arm in baseline.LIMITS:
            point, previous = result['totals'][arm], old['totals'][arm]
            if (point['baselinePaidLookups'] != previous['paidLookups'] or point['holdoutPasses'] != previous['holdoutPasses']
                    or point['baselineExtraValidationLookups'] != previous.get('extraValidationLookups', 0)):
                raise ValueError('The skipped-read comparison must reproduce its previous totals')
            output[arm] = {'totals': point, 'comparison': result['comparisons'][arm]}
        return output

    math = {dataset: {setting: selected(result, reference['math'][dataset][setting])
                      for setting, result in groups.items()} for dataset, groups in report['math'].items()}
    transfers = {cohort: selected(result, reference['transfer'][cohort]) for cohort, result in report['transfer'].items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'math': math, 'transfer': transfers}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, parent, math_data, transfer_data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, parent, math_data, transfer_data, reference)
    with args.out.open('x') as file:
        json.dump(report, file, sort_keys=True, indent=2)
        file.write('\n')


if __name__ == '__main__':
    main()
