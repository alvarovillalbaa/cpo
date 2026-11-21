"""Require a fresh validation witness before one stalled-search admission."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_no_nominee_admission as prior
from benchmarks.witness_admission_retry import outcomes as retry_outcomes
from cpo import Row
from cpo._contract import digest
from cpo.halving.funded_admission import qualify_with_funded_retry
from cpo.rotating_witness.episode import WitnessCycle


ROOT, RANKING, retry, FULL, CAP = prior.ROOT, prior.RANKING, prior.retry, prior.FULL, prior.CAP
REFERENCE = 'docs/witness-no-nominee-admission-results-v1.json'
REFERENCE_SHA256 = '35f71d674a1a9ea4ac5e88de89f4a4222bde77f8da4c62e76954559486c8f8ad'
CAPPED, FIRST, PEER = 'eligible-direct/23', 'first-miss-probe', 'peer-miss-probe'
METHODS = (retry.BASE, FULL, prior.RATE, CAPPED, FIRST, PEER)


def prepare():
    upstream, _, data = prior.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(upstream):
        raise ValueError('Use the published no-nominee search and proof benchmark')
    plan = {'protocol': 'witness-no-nominee-miss-v1', 'parentPlanSha256': digest(upstream),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'combinedCap': CAP, 'fallbackValidationCap': upstream['fallbackValidationCap'],
            'pairedCaseDraws': upstream['pairedCaseDraws'], 'resamplingSeed': upstream['resamplingSeed'],
            'rule': 'At a no-nominee stop, keep the supported-rate nominee fixed. Probe one already observed '
                    'incumbent miss that the nominee has not answered in its own validation panel. Open its '
                    'assigned proof only after a pass. Charge the new grade within the original 24-lookup cap.',
            'caseOrder': 'Use either scheduled case order or descending smoothed paid pass rate among other '
                         'non-incumbent prompts on the case. Break ties in scheduled order.',
            'matchedControl': 'Use the same eligible episodes and the same 23-lookup proof limit without a probe.',
            'fit': 'Fit on the other family by promotions within seeded spend, then lower spend.',
            'gate': 'Require a positive paired lower endpoint against the single proof within seeded spend.'}
    return plan, reference, data


def choose_cases(start, candidate, validation, grades):
    available = [case for case in validation if grades.get((start, case)) is False and (candidate, case) not in grades]
    if not available:
        return None
    peers = {case: Counter() for case in available}
    for (prompt, case), passed in grades.items():
        if prompt not in (start, candidate) and case in peers:
            peers[case].update(passes=passed, reads=1)
    supported = max(available, key=lambda case: Fraction(peers[case]['passes'] + 1, peers[case]['reads'] + 2))
    return available[0], supported


def screen(start, candidate, case, grade, evidence, prove):
    if (candidate, case) in evidence or evidence.get((start, case)) is not False:
        raise ValueError('A probe needs a known incumbent miss and an unread candidate grade')
    passed = grade(candidate, case)
    if type(passed) is not bool:
        raise ValueError('A probe grade must be an exact boolean')
    if not passed:
        return retry.Decision(start, 1, 'rejected'), False
    second = prove(candidate, {**evidence, (candidate, case): passed}, CAP - 1)
    return retry.Decision(second.prompt, second.lookups + 1, second.status), True


def outcomes(matrix, held, start, layouts, plan, policy, nomination, activity):
    previous = retry_outcomes(matrix, held, start, layouts, plan, policy, nomination)
    original = previous[FULL]
    result = {retry.BASE: previous[retry.BASE], FULL: original,
              **dict.fromkeys((prior.RATE, CAPPED, FIRST, PEER), original)}
    if nomination.original is not None:
        return result
    activity['noNominee'] += 1
    enrolled = [prompt for layout in layouts for prompt in layout['alternatives']]
    selected, _ = prior.choose(start, enrolled, nomination.grades)
    candidate = selected[prior.RATE]
    if candidate is None:
        return result
    activity['supportedRateNominees'] += 1
    chosen_layout = next(layout for layout in layouts if candidate in layout['alternatives'])
    cycles = tuple(WitnessCycle(tuple(layout['alternatives']), tuple(Row(str(case), 'task') for case in layout['validation']),
                                tuple(Row(str(case), 'task') for case in layout['qualify']), layout['seed'])
                   for layout in layouts)
    held_set = set(held)

    def grade(prompt, case):
        if case in held_set:
            raise ValueError('The policy cannot read the holdout')
        return matrix[int(prompt)][case] == '1'

    def prove(prompt, grades, cap):
        ledger = {(key, str(case)): passed for (key, case), passed in grades.items()}
        checked = qualify_with_funded_retry(
            start, prompt, cycles, lambda key, row, _: grade(key, int(row.id)), ledger,
            minimum_retry_lookups=CAP + 1, evaluation_limit=cap,
            maximum_extension_rows=plan['maximumExtensionRows'], minimum_gain=plan['minimumQualificationGain'])
        return retry.Decision(checked.prompt, checked.qualification_evaluations, checked.first.status)

    result[prior.RATE] = prove(candidate, nomination.grades, CAP)
    offered = choose_cases(start, candidate, chosen_layout['validation'], nomination.grades)
    if offered is None:
        return result
    activity['probeEligible'] += 1
    activity['caseOrderDifferences'] += int(offered[0] != offered[1])
    result[CAPPED] = prove(candidate, nomination.grades, CAP - 1)
    for method, case in zip((FIRST, PEER), offered, strict=True):
        result[method], passed = screen(start, candidate, case, grade, nomination.grades, prove)
        activity[f'{method}/passes'] += int(passed)
    return result


def execute(plan, reference, data):
    measured, activity = {}, {}
    for phase in RANKING.PHASES:
        counts = Counter()

        def run(*args):
            return outcomes(*args, counts)

        with patch.multiple(retry, METHODS=METHODS, outcomes=run):
            measured[phase] = retry.measure(*data[phase], plan['fallbackValidationCap'])
        activity[phase] = counts
    bbh = RANKING.gap.paired.BBH
    with patch.object(retry, 'METHODS', METHODS):
        fit = {bbh: retry.train(list(measured[bbh][0].values())), 'mmlu': retry.train(
            [item for phase in RANKING.gap.paired.replay.PHASES for item in measured[phase][0].values()])}
    cohorts = {}
    for phase, (groups, traces) in measured.items():
        prior_row = reference['cohorts'][phase]
        counts = activity[phase]
        if (counts['noNominee'], counts['supportedRateNominees']) != (prior_row['activity']['noNominee'],
                                                                     prior_row['activity'][f'{prior.RATE}/attempted']):
            raise ValueError('The no-nominee eligibility counts changed')
        totals = {method: sum((group['counts'][method] for group in groups.values()), Counter()) for method in METHODS}
        for method in (retry.BASE, FULL, prior.RATE):
            if any(totals[method][key] != prior_row['totals'][method].get(key, 0)
                   for key in ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
                raise ValueError('The original single-proof or supported-rate total changed')
        votes = {task: {'cases': item['cases'], 'decisionsPerCase': item['decisionsPerCase']} for task, item in groups.items()}
        selected = fit['mmlu' if phase == bbh else bbh]['selected']
        pairs = {}
        for method, control in ((selected, FULL), (FIRST, CAPPED), (PEER, CAPPED), (PEER, FIRST)):
            with patch.object(RANKING.paired_bands, 'BASELINE', control):
                pairs[f'{method} vs {control}'] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
        cohorts[phase] = {'totals': totals, 'activity': counts, 'selectedOutsideFamily': selected,
                          'paired': pairs, 'panelTraceSha256': traces,
                          'qualifies': totals[selected]['paidLookups'] <= totals[retry.BASE]['paidLookups']
                          and pairs[f'{selected} vs {FULL}']['interval95PercentagePoints'][0] > 0}
    return {'plan': plan, 'planSha256': digest(plan), 'training': fit, 'cohorts': cohorts,
            'newProviderRequests': 0, 'qualifies': all(row['qualifies'] for row in cohorts.values())}


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
