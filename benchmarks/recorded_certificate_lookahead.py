"""Spend a bounded validation allowance seeking a two-pass certificate."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_first_certificate_transfer as transfer, recorded_first_training_certificate as core
from cpo import Row
from cpo._contract import digest


parent, math, backup = core.parent, core.math, core.backup
ARCHIVE_RECEIPT = 'docs/recorded-first-training-certificate-results-v1.json'
ARCHIVE_SHA256 = 'ec23a9fba84c50f7a69bec6c0af41e68df674a5f3fd6425e8b2c5e1446fb7897'
TRANSFER_RECEIPT = 'docs/recorded-first-certificate-transfer-results-v1.json'
TRANSFER_SHA256 = '42e3bb7943311efd6784ce5e9494c6aa2c35a8d712f253af2198c71fbff3b748'
LIMITS = {'one-panel-lookahead': 1, 'two-panel-lookahead': 2}


def search_for_stronger(incumbent, first, roster, rows, training, observe, ledger, *, cap, extra):
    """Preserve a certified fallback if the allowed reads prove no two-pass gain."""
    base = {row.id: ledger[incumbent, row.id].passed for row in rows}
    target = sum(base.values()) + 2
    if target > len(rows):
        return first, False
    protected = {row.id for row in rows if row.critical and base[row.id]}
    remaining_budget = len(ledger) + extra
    row_ids = set(base)
    hits, reads = Counter(), Counter()
    for (_, case), reply in ledger.items():
        if case in row_ids:
            hits[case] += reply.passed
            reads[case] += 1

    for prompt in roster[roster.index(first):]:
        evidence = {row.id: ledger[prompt, row.id].passed for row in rows if (prompt, row.id) in ledger}
        if any(evidence.get(case) is False for case in protected):
            continue
        passed = sum(evidence.values())
        unknown = [row for row in rows if row.id not in evidence]
        missing = protected - evidence.keys()
        if passed >= target and not missing:
            return prompt, True
        reserve = sum((name, row.id) not in ledger for name in (incumbent, prompt) for row in training)
        stop = min(remaining_budget, cap - reserve)
        ordered = sorted(unknown, key=lambda row: (
            row.id not in missing, Fraction(hits[row.id] + 1, reads[row.id] + 2)))
        for offset, row in enumerate(ordered):
            needed = max(target - passed, len(missing))
            if needed > min(len(ordered) - offset, stop - len(ledger)):
                break
            correct = observe(prompt, row).passed
            if type(correct) is not bool:
                raise ValueError('Validation requires exact boolean grades')
            hits[row.id] += correct
            reads[row.id] += 1
            passed += correct
            if row.id in missing:
                if not correct:
                    break
                missing.remove(row.id)
            if passed >= target and not missing:
                return prompt, True
    return first, False


def trial(cells, start, roster, cohorts, seed, cap, arm):
    training = tuple(Row(str(case), 'training') for case in cohorts[0][:len(cohorts[0]) // 2])
    audit = Counter()

    def choose(incumbent, candidates, rows, observe, ledger, *, method, cap):
        gain = next(core.certificates(incumbent, candidates, rows, training, observe, ledger, cap), None)
        if gain is None:
            return incumbent, False
        first, _ = gain
        before = len(ledger)
        extra = LIMITS[arm] * len(rows)
        selected, strong = search_for_stronger(incumbent, first, candidates, rows, training, observe, ledger,
                                              cap=cap, extra=extra)
        if len(ledger) - before > extra:
            raise ValueError('The extra validation proof exceeded its allowance')
        audit.update(firstCertificates=1, strongerCertificates=int(strong),
                     differentNominees=int(first != selected), extraValidationLookups=len(ledger) - before)
        return selected, False

    # Additional paid evidence may change the nominee, but never adds a second proof attempt.
    with (patch.object(math, 'select', choose), patch.object(backup, 'strongest_backup', lambda *_, **_kw: None)):
        point, trace, grades = parent.run_trial(cells, start, roster, cohorts, seed, cap, core.prior.CANDIDATE,
                                              parent.EXPECTED)
    return {**point, **audit}, trace, grades


def read_reference(name, expected, plan):
    raw = (transfer.ROOT / name).read_bytes()
    result = json.loads(raw)
    if sha256(raw).hexdigest() != expected or result['planSha256'] != digest(plan):
        raise ValueError('Use the exact published first-certificate reference')
    return result


def prepare():
    original, data, math_reference = core.prepare()
    transfer_plan, panels = transfer.prepare()
    archived = read_reference(ARCHIVE_RECEIPT, ARCHIVE_SHA256, original)
    transferred = read_reference(TRANSFER_RECEIPT, TRANSFER_SHA256, transfer_plan)
    plan = {**{key: transfer_plan[key] for key in ('gepaVersion', 'searchCap', 'minimumLookupSavingPercent',
                                                  'bootstrapSeed', 'bootstrapDraws', 'seeds', 'challengers',
                                                  'caseCounts', 'panels')},
            'protocol': 'recorded-certificate-lookahead-v1', 'mathPlanSha256': digest(original),
            'transferPlanSha256': digest(transfer_plan), 'mathReceiptSha256': ARCHIVE_SHA256,
            'transferReceiptSha256': TRANSFER_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'validationAllowancesInPanelWidths': LIMITS,
            'scope': 'Keep the same first certificate and use a bounded additional validation budget to seek a '
                     'two-pass lower bound against the incumbent. Reuse the first prompt as a fallback. Keep '
                     'the original single training and qualification attempt. Test on the original archived math '
                     'and transfer schedules with frozen controls.'}
    return plan, (original, data, math_reference, archived), (panels, transferred)


def replay(plan, math_data, transfer_data):
    original, data, math_reference, archived = math_data
    panels, transferred = transfer_data
    baseline_trial = core.trial
    original_math_arms, original_transfer_arms = core.ARMS, transfer.METHODS

    def choice(cells, start, roster, cohorts, seed, cap, arm):
        callback = trial if arm in LIMITS else baseline_trial
        return callback(cells, start, roster, cohorts, seed, cap, arm)

    with patch.object(core, 'trial', choice):
        with patch.multiple(core, ARMS=(*original_math_arms, *LIMITS), POLICIES=(*core.POLICIES, *LIMITS)):
            math_report = core.replay(original, data, math_reference)['results']
        with patch.object(transfer, 'METHODS', (*original_transfer_arms, *LIMITS)):
            transfer_report = transfer.replay(plan, panels)['cohorts']
    for dataset, groups in math_report.items():
        for setting, result in groups.items():
            reference = archived['results'][dataset][setting]['totals']
            if any(result['totals'][arm] != reference[arm] for arm in original_math_arms):
                raise ValueError('The original math comparison failed to reproduce')
    for cohort, result in transfer_report.items():
        prior = transferred['cohorts'][cohort]
        for panel, details in result['panels'].items():
            if any(details['totals'][arm] != prior['panels'][panel]['totals'][arm] for arm in original_transfer_arms):
                raise ValueError('The original transfer panel failed to reproduce')
        totals = result['totals']
        vectors = result['caseVectorsBySubject']
        result['comparisons'] = {}
        for arm in LIMITS:
            target = {**totals, core.FIRST: totals[arm]}
            paired = {subject: {**rows, core.FIRST: rows[arm]} for subject, rows in vectors.items()}
            result['comparisons'][arm] = transfer.compare(plan, target, paired)
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'math': math_report, 'transfer': transfer_report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, math_data, transfer_data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, math_data, transfer_data)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
