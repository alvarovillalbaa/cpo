"""Use a bounded validation proof against the first certified nominee."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_certificate_lookahead as baseline, recorded_certificate_lookahead_pruning as pruning
from cpo._contract import digest
from cpo.opening_validation import certify_opening_validation


LIMITS = {'later-first-one-panel': 1, 'later-first-two-panels': 2,
          'head-to-head-one-panel': 1, 'head-to-head-two-panels': 2}
PRUNED_RECEIPT = 'docs/recorded-certificate-lookahead-pruning-results-v1.json'
PRUNED_SHA256 = '7d0c1d35f27f548b3d03a81fbe063ac24b50ce7d12e1cfcf7e64fe09d2894407'
original_search = baseline.search_for_stronger


class ProofAllowanceUsed(Exception):
    """The comparison reached its cap before the next validation reply."""


def can_still_win(first, challenger, rows, ledger, available):
    def counts(prompt):
        paid = [ledger[prompt, row.id].passed for row in rows if (prompt, row.id) in ledger]
        passed = sum(paid)
        return passed, passed + len(rows) - len(paid)

    first_lower, first_upper = counts(first)
    challenger_lower, challenger_upper = counts(challenger)
    return challenger_upper > first_lower and available >= max(0, first_upper - challenger_lower + 1)


def search_later(incumbent, first, roster, rows, training, observe, ledger, *, cap, extra, paired):
    deadline = len(ledger) + extra
    for challenger in roster[roster.index(first) + 1:]:
        reserve = sum((name, row.id) not in ledger for name in (incumbent, challenger) for row in training)
        stop = min(deadline, cap - reserve)
        if paired and not can_still_win(first, challenger, rows, ledger, stop - len(ledger)):
            continue
        _, strong = original_search(incumbent, challenger, (challenger,), rows, training, observe, ledger,
                                    cap=cap, extra=max(0, deadline - len(ledger)))
        if not strong:
            continue
        if not paired:
            return challenger, True
        if not can_still_win(first, challenger, rows, ledger, stop - len(ledger)):
            continue

        def buy(prompt, row):
            if len(ledger) >= stop:
                raise ProofAllowanceUsed
            return observe(prompt, row)

        try:
            if certify_opening_validation(first, challenger, rows, ledger, buy):
                return challenger, True
        except ProofAllowanceUsed:
            pass
    return first, False


def prepare():
    previous, parent, math_data, transfer_data, _ = pruning.prepare()
    paid = baseline.read_reference(PRUNED_RECEIPT, PRUNED_SHA256, previous)
    plan = {'protocol': 'recorded-certificate-head-to-head-v1', 'parentPlanSha256': digest(previous),
            'parentReceiptSha256': PRUNED_SHA256, 'gepaVersion': parent['gepaVersion'],
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'pairedProofSourceSha256': sha256((baseline.transfer.ROOT / 'cpo/opening_validation.py').read_bytes()).hexdigest(),
            'lookaheadAllowancesInPanelWidths': LIMITS,
            'scope': 'Skip early extension of the first certificate. Search the later roster for the same '
                     'two-pass lower bound. Compare replacing on that certificate with also proving a strict '
                     'gain against the first candidate. Both proofs share the same lookup allowance and '
                     'retain the existing training reserve and single qualification attempt.'}
    return plan, parent, math_data, transfer_data, paid


def execute(plan, parent, math_data, transfer_data, reference):
    old_trial, old_arms = baseline.trial, tuple(baseline.LIMITS)
    pruning_only = {'pairedDecisionsChecked', 'baselinePaidLookups', 'baselineExtraValidationLookups',
                    'validationLookupsSaved', 'qualificationLookupDelta'}

    def trial(*arguments):
        arm = arguments[-1]
        policy = (partial(search_later, paired=arm.startswith('head-to-head')) if arm in LIMITS else pruning.prune)
        with patch.object(baseline, 'search_for_stronger', policy):
            return old_trial(*arguments)

    with (patch.object(baseline, 'LIMITS', {**baseline.LIMITS, **LIMITS}), patch.object(baseline, 'trial', trial)):
        full = baseline.replay(parent, math_data, transfer_data)

    def select(result, previous):
        for arm in old_arms:
            published = {key: value for key, value in previous[arm]['totals'].items() if key not in pruning_only}
            if published != result['totals'][arm] or previous[arm]['comparison'] != result['comparisons'][arm]:
                raise ValueError('The pruned reference must replay before comparing alternate policies')
        return {'totals': {arm: result['totals'][arm] for arm in (*old_arms, *LIMITS)},
                'comparisons': {arm: result['comparisons'][arm] for arm in (*old_arms, *LIMITS)}}

    math = {name: {setting: select(result, reference['math'][name][setting]) for setting, result in groups.items()}
            for name, groups in full['math'].items()}
    transfer = {cohort: select(result, reference['transfer'][cohort]) for cohort, result in full['transfer'].items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'math': math, 'transfer': transfer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, parent, math_data, transfer_data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, parent, math_data, transfer_data, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
