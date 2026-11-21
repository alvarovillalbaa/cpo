"""Reserve room for a second independent admission before the first proof starts."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_admission_retry as retry
from benchmarks.witness_admission_retry import outcomes as retry_outcomes
from cpo._contract import digest


ROOT, REPLAY, RANKING = retry.ROOT, retry.REPLAY, retry.RANKING
REFERENCE = 'docs/witness-admission-retry-results-v1.json'
REFERENCE_SHA256 = '07828106ff3d0660d4225af9e3b588d862e1dbc5fc8513b0ed1f0ee494398490'
CAP = 24
FULL, EXACT = 'expected-reads/24', 'retry/24'
RESERVED, FUTILITY = 'reserved/24', 'reserved-futility/24'
METHODS = (retry.BASE, FULL, EXACT, RESERVED, FUTILITY)
FIELDS = ('holdoutPasses', 'paidLookups', 'proofLookups', 'proofCapped', 'promotions', 'retries', 'retryLookups',
          'retryPromotions')


def prepare():
    parent, _, _, data = retry.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published independent retry controls')
    plan = {'protocol': 'witness-proof-split-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'jointProofCap': CAP,
            'methods': METHODS, 'fallbackValidationCap': parent['fallbackValidationCap'],
            'pairedCaseDraws': parent['pairedCaseDraws'], 'resamplingSeed': parent['resamplingSeed'],
            'rule': 'Fix the paid rival and an independent panel before reading the first proof. Reserve the '
                    'minimum budget that can certify this rival. Transfer unused credit if the first proof '
                    'does not promote. The futility variant returns credit before another read when even '
                    'perfect remaining grades cannot certify the first nominee within its allocation.',
            'gate': 'Fit on other-family promotions and realized proof spend. Require a positive paired '
                    'lower endpoint against full expected-read proof and no greater cost than full seeded proof.'}
    return plan, reference, data


class _NoAffordableCertificate(Exception):
    pass


def bounded_first(start, nominee, current, reserve, evaluate, grades, minimum, limit, stop_early):
    if stop_early and limit >= 2 * len(current):
        raise ValueError('The first allowance must exclude a completed base tie')
    reads, lower = 0, -len(current)

    def grade(prompt, case):
        nonlocal reads, lower
        if stop_early and lower + limit - reads < minimum:
            raise _NoAffordableCertificate
        passed = evaluate(prompt, case)
        reads += 1
        lower += passed if prompt == nominee else not passed
        return passed

    try:
        first = retry.scalar_proof(start, nominee, current, reserve, grade, grades, minimum, limit)
    except _NoAffordableCertificate:
        return retry.Decision(start, reads, 'budget-futile')
    return retry.Decision(first.prompt, reads, first.status)


def split_proof(start, nominee, rival, current, reserve, backup, spare, grade, grades, minimum, cap, stop_early):
    if (set(current) | set(reserve)) & (set(backup) | set(spare)):
        raise ValueError('Proofs must have disjoint allotted cases')
    limit = cap - len(backup) - minimum
    if limit < 0:
        raise ValueError('The joint cap cannot fund a minimum rival certificate')
    first = bounded_first(start, nominee, current, reserve, grade, grades, minimum, limit, stop_early)
    if first.status == 'promoted':
        return first
    second = retry.scalar_proof(start, rival, backup, spare, grade, grades, minimum, cap - first.lookups)
    paid = len(second.observations)
    if first.lookups + paid > cap:
        raise ValueError('Both proofs must fit the original joint cap')
    return retry.Decision(second.prompt, first.lookups + paid, second.status, True, paid)


def outcomes(matrix, held, start, layouts, plan, policy, nomination):
    original = retry_outcomes(matrix, held, start, layouts, plan, policy, nomination)
    results = {method: original[method] for method in (retry.BASE, FULL, EXACT)}
    results.update({RESERVED: results[FULL], FUTILITY: results[FULL]})
    nominee = nomination.original
    if nominee is None:
        return results
    rival = retry.ranked_rival(layouts, nominee, nomination.grades)
    if rival is None:
        return results

    roster = {prompt: index for index, layout in enumerate(layouts) for prompt in layout['alternatives']}
    cycle = roster[nominee]
    current = layouts[cycle]['qualify']
    reserve = [case for layout in layouts[:cycle] for case in layout['qualify']][:plan['maximumExtensionRows']]
    retired = set(current) | set(reserve)
    index = retry.retry_panel(layouts, roster[rival], retired)
    if index is None:
        return results
    backup = layouts[index]['qualify']
    spare = [case for layout in layouts[:index] for case in layout['qualify'] if case not in retired][
        :plan['maximumExtensionRows']]

    def grade(prompt, case):
        return matrix[int(prompt)][case] == '1'

    for method, stop_early in ((RESERVED, False), (FUTILITY, True)):
        results[method] = split_proof(start, nominee, rival, current, reserve, backup, spare, grade, nomination.grades,
                                      plan['minimumQualificationGain'], CAP, stop_early)
    if results[RESERVED].prompt == nominee and results[FUTILITY] != results[RESERVED]:
        raise ValueError('Futility cannot lose a certified first promotion')
    return results


def summarize(groups, plan, reference, winner):
    totals, paired = {}, {}
    votes = {name: {'cases': unit['cases'], 'decisionsPerCase': unit['decisionsPerCase']} for name, unit in groups.items()}
    for method in METHODS:
        counts = sum((unit['counts'][method] for unit in groups.values()), Counter())
        totals[method] = {key: counts[key] for key in FIELDS}
        if method in (retry.BASE, FULL, EXACT) and any(
                counts[key] != reference['totals'][method].get(key, 0) for key in FIELDS):
            raise ValueError('The published proof and retry controls changed')
    comparisons = ((RESERVED, FULL), (FUTILITY, FULL), (FUTILITY, EXACT), (FUTILITY, RESERVED), (winner, FULL))
    for method, control in dict.fromkeys(comparisons):
        with patch.object(RANKING.paired_bands, 'BASELINE', control):
            paired[f'{method} vs {control}'] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
    return {'totals': totals, 'paired': paired, 'selectedOutsideFamily': winner,
            'qualifies': winner in (RESERVED, FUTILITY) and totals[winner]['paidLookups'] <= totals[retry.BASE]['paidLookups']
            and paired[f'{winner} vs {FULL}']['interval95PercentagePoints'][0] > 0}


def execute(plan, reference, data):
    with patch.multiple(retry, METHODS=METHODS, outcomes=outcomes):
        replayed = {phase: retry.measure(*data[phase], plan['fallbackValidationCap']) for phase in RANKING.PHASES}
        bbh = RANKING.gap.paired.BBH
        fit = {bbh: retry.train(list(replayed[bbh][0].values())), 'mmlu': retry.train(
            [unit for phase in RANKING.gap.paired.replay.PHASES for unit in replayed[phase][0].values()])}
    cohorts = {phase: {**summarize(groups, plan, reference['cohorts'][phase],
                                  fit['mmlu' if phase == bbh else bbh]['selected']), 'panelTraceSha256': traces}
               for phase, (groups, traces) in replayed.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'training': fit,
            'cohorts': cohorts, 'qualifies': all(cohort['qualifies'] for cohort in cohorts.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
