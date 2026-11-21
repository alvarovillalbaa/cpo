"""Fund exact-rejection retries using only evidence available before the retry."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_admission_retry as retry, witness_same_case_order as prior
from benchmarks.witness_admission_retry import outcomes as retry_outcomes
from cpo._contract import digest


ROOT, RANKING = retry.ROOT, retry.RANKING
REFERENCE = 'docs/witness-admission-retry-results-v1.json'
REFERENCE_SHA256 = '07828106ff3d0660d4225af9e3b588d862e1dbc5fc8513b0ed1f0ee494398490'
PARENT = 'docs/witness-same-case-order-results-v1.json'
PARENT_SHA256 = '42f047f26627dc3d9942f8aea58b634c5910198fcf02d28ed68e3c6f23b7d7b3'
CAP = 24
FULL, EXACT = f'expected-reads/{CAP}', f'retry/{CAP}'
GATES = {
    'at-least-12': (12, None),
    'at-least-14': (14, None),
    'paired-gain': (0, 'paired'),
    'smoothed-gain': (0, 'smoothed'),
    'smoothed-gain-and-12': (12, 'smoothed'),
}
METHODS = (retry.BASE, FULL, EXACT, *GATES)
FIELDS = ('holdoutPasses', 'paidLookups', 'proofLookups', 'proofCapped', 'promotions', 'retries', 'retryLookups',
          'retryPromotions')


def prepare():
    parent, _, _, data = prior.prepare()
    raw, parent_raw = (ROOT / REFERENCE).read_bytes(), (ROOT / PARENT).read_bytes()
    expected = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or sha256(parent_raw).hexdigest() != PARENT_SHA256 or (
            json.loads(parent_raw)['planSha256'] != digest(parent) or parent['jointProofCap'] != CAP):
        raise ValueError('Use the published exact-rejection and proof-ordering results')
    plan = {'protocol': 'witness-retry-funding-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': PARENT_SHA256, 'referenceSha256': REFERENCE_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'methods': METHODS, 'gates': GATES,
            'fallbackValidationCap': parent['fallbackValidationCap'], 'jointProofCap': parent['jointProofCap'],
            'pairedCaseDraws': parent['pairedCaseDraws'], 'resamplingSeed': parent['resamplingSeed'],
            'rule': 'Let the original first proof settle. After exact rejection, consider only its original '
                    'eligible rival and independent panel. Use remaining reads and paid search scores to decide '
                    'which retries to fund. Retain the start when the retry is skipped.',
            'fit': 'On the other family, maximize exact promotions within realized seeded proof spend. '
                   'Break ties by lower proof spend, then the declared order. Holdout plays no part in selection.',
            'gate': 'Require a positive subject-and-case paired lower endpoint against full expected-read single '
                    'proof, and realized total spend no higher than the original seeded single proof.'}
    return plan, expected, data


def paid_gains(start, rival, grades):
    old = {case: passed for (prompt, case), passed in grades.items() if prompt == start}
    new = {case: passed for (prompt, case), passed in grades.items() if prompt == rival}
    common = old.keys() & new.keys()
    paired = sum(new[case] - old[case] for case in common) > 0
    smoothed = Fraction(sum(new.values()) + 1, len(new) + 2) > Fraction(sum(old.values()) + 1, len(old) + 2)
    return {'paired': paired, 'smoothed': smoothed}


def gate_choices(start, first, rival, grades, cap):
    if first.status != 'rejected':
        return ()
    gains = paid_gains(start, rival, grades)
    remaining = cap - first.lookups
    return tuple(name for name, (minimum, signal) in GATES.items()
                 if remaining >= minimum and (signal is None or gains[signal]))


def outcomes(matrix, held, start, layouts, plan, policy, nomination):
    original = retry_outcomes(matrix, held, start, layouts, plan, policy, nomination)
    first, second = original[FULL], original[EXACT]
    result = {method: original[method] for method in (retry.BASE, FULL, EXACT)}
    result.update(dict.fromkeys(GATES, first))
    if second.retry:
        if first.status != 'rejected' or first.lookups != second.lookups - second.retry_lookups:
            raise ValueError('A funded retry must preserve the settled full first proof')
        rival = retry.ranked_rival(layouts, nomination.original, nomination.grades)
        chosen = gate_choices(start, first, rival, nomination.grades, CAP)
        result.update(dict.fromkeys(chosen, second))
    return result


def summarize(groups, plan, reference, winner):
    totals = {}
    for method in METHODS:
        counts = sum((group['counts'][method] for group in groups.values()), Counter())
        totals[method] = {key: counts[key] for key in FIELDS}
        if method in (retry.BASE, FULL, EXACT) and any(
                counts[key] != reference['totals'][method].get(key, 0) for key in FIELDS):
            raise ValueError('The published seeded, single, or exact-retry totals changed')
    votes = {subject: {'cases': group['cases'], 'decisionsPerCase': group['decisionsPerCase']}
             for subject, group in groups.items()}
    with patch.object(RANKING.paired_bands, 'BASELINE', FULL):
        paired = RANKING.paired_bands.paired_ranges(votes, winner, plan)['subjectsAndCases']
    return {'totals': totals, 'selectedOutsideFamily': winner, 'pairedSelectedVsSingle': paired,
            'qualifies': totals[winner]['paidLookups'] <= totals[retry.BASE]['paidLookups']
            and paired['interval95PercentagePoints'][0] > 0}


def execute(plan, reference, data):
    with patch.multiple(retry, METHODS=METHODS, outcomes=outcomes):
        replayed = {phase: retry.measure(*data[phase], plan['fallbackValidationCap']) for phase in RANKING.PHASES}
        bbh = RANKING.gap.paired.BBH
        fit = {bbh: retry.train(list(replayed[bbh][0].values())), 'mmlu': retry.train(
            [group for phase in RANKING.gap.paired.replay.PHASES for group in replayed[phase][0].values()])}
    cohorts = {phase: {**summarize(groups, plan, reference['cohorts'][phase],
                                    fit['mmlu' if phase == bbh else bbh]['selected']), 'panelTraceSha256': traces}
               for phase, (groups, traces) in replayed.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'training': fit,
            'cohorts': cohorts, 'qualifies': all(group['qualifies'] for group in cohorts.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
