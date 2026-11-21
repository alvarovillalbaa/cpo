"""Test a second independent proof inside the original admission allowance."""

import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_budgeted_admission as previous
from cpo import Row
from cpo._contract import digest


ROOT, REPLAY = previous.ROOT, previous.REPLAY
RANKING = previous.previous.earlier
REFERENCE = 'docs/witness-budgeted-admission-results-v1.json'
REFERENCE_SHA = 'a2b695aa9c1c54d82bf4e34c795fa7793dedc119ce881883d981c2a596c3bfcf'
CAPS = (20, 24)
BASE = previous.BASE
METHODS = (BASE, *(f'{name}/{cap}' for name in ('expected-reads', 'retry') for cap in CAPS))


@dataclass(frozen=True)
class Decision:
    prompt: str
    lookups: int
    status: str
    retry: bool = False
    retry_lookups: int = 0


def prepare():
    parent, _, native, data = previous.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or reference['planSha256'] != digest(parent):
        raise ValueError('Use the published capped admission replay')
    plan = {'protocol': 'witness-admission-retry-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': REFERENCE_SHA, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'fallbackValidationCap': parent['fallbackValidationCap'], 'pairedCaseDraws': parent['pairedCaseDraws'],
            'resamplingSeed': parent['resamplingSeed'], 'caps': CAPS, 'methods': METHODS,
            'rule': 'After an exact rejection, choose the strongest already-read rival by smoothed validation rate. '
                    'Prefer its full unused panel, then the earliest full unused panel. Allocate one independent '
                    'proof only if its minimum promotion certificate fits the remaining allowance.',
            'gate': 'Fit on other-family admission counts and cost. Require a positive paired range against '
                    'full expected-read proof and no greater realized cost than full seeded proof on every cohort.'}
    return plan, reference, native, data


def ranked_rival(layouts, original, grades):
    counts = {}
    for (prompt, _), passed in grades.items():
        counts.setdefault(prompt, Counter()).update(passes=passed, reads=1)
    candidates = [prompt for layout in layouts for prompt in layout['alternatives'] if prompt != original and prompt in counts]
    return max(candidates, default=None,
               key=lambda prompt: Fraction(counts[prompt]['passes'] + 1, counts[prompt]['reads'] + 2))


def retry_panel(layouts, enrolled, retired):
    order = (enrolled, *(index for index in range(len(layouts)) if index != enrolled))
    return next((index for index in order if not retired.intersection(layouts[index]['qualify'])), None)


def scalar_proof(start, candidate, current, reserve, grade, evidence, minimum, cap):
    counts = []
    for prompt in (start, candidate):
        observed = [passed for (key, _), passed in evidence.items() if key == prompt]
        counts.append((sum(observed), len(observed)))
    return previous.SELECTORS['expected-reads'](
        start, candidate, [Row(str(case), 'task') for case in current],
        lambda p, row, _: grade(p, int(row.id)), reserve=[Row(str(case), 'task') for case in reserve],
        validation_counts=counts, minimum_gain=minimum, evaluation_limit=cap)


def try_retry(first, cap, start, original, reserve, layouts, roster, plan, grades, evaluate):
    used = len(first.observations)
    previous_decision = Decision(first.prompt, used, first.status)
    if first.status != 'rejected':
        return previous_decision
    rival = ranked_rival(layouts, original, grades)
    if rival is None:
        return previous_decision
    retired = set(layouts[roster[original]]['qualify'])
    if first.used_reserve:
        retired.update(reserve)
    index = retry_panel(layouts, roster[rival], retired)
    if index is None:
        return previous_decision
    current = layouts[index]['qualify']
    minimum = plan['minimumQualificationGain']
    remaining = cap - used
    if remaining < len(current) + minimum:
        return previous_decision
    earlier = [case for layout in layouts[:index] for case in layout['qualify'] if case not in retired]
    spare = earlier[:plan['maximumExtensionRows']]
    second = scalar_proof(start, rival, current, spare, evaluate, grades, minimum, remaining)
    reads = len(second.observations)
    if reads > remaining or {int(row.row_id) for row in second.observations} & retired:
        raise ValueError('The retry left its budget or reused a retired admission case')
    return Decision(second.prompt, used + reads, second.status, True, reads)


def outcomes(matrix, held, start, layouts, plan, policy, nomination):
    original = nomination.original
    if original is None:
        return dict.fromkeys(METHODS, Decision(start, 0, 'no-nominee'))
    roster = {prompt: index for index, layout in enumerate(layouts) for prompt in layout['alternatives']}
    cycle = roster[original]
    layout = layouts[cycle]
    current = layout['qualify']
    earlier = [case for item in layouts[:cycle] for case in item['qualify']]
    reserve = earlier[:plan['maximumExtensionRows']]
    all_proof = {case for item in layouts for case in item['qualify']}
    if all_proof & (set(held) | {case for _, case in nomination.grades}):
        raise ValueError('Admission panels overlap paid validation or holdout')
    if plan['qualificationPolicy'] != 'extend-ties':
        raise ValueError('Use the original independent proof and tie rule')

    def grade(prompt, case):
        if case not in all_proof:
            raise ValueError('Admission left its independent cases')
        return matrix[int(prompt)][case] == '1'

    baseline, proof, stopped = previous.previous.admit(
        start, original, current, earlier, grade, plan=plan, seed=layout['seed'],
        recycle=policy == 'recycle-unread', remaining=24)
    result = {BASE: Decision(baseline, proof, 'undecided' if stopped else
                             'promoted' if baseline != start else 'rejected')}
    for cap in CAPS:
        first = scalar_proof(start, original, current, reserve, grade, nomination.grades,
                             plan['minimumQualificationGain'], cap)
        result[f'expected-reads/{cap}'] = Decision(first.prompt, len(first.observations), first.status)
        result[f'retry/{cap}'] = try_retry(first, cap, start, original, reserve, layouts, roster,
                                          plan, nomination.grades, grade)
    return result


def measure(inputs, panels, _native, _conditions, cap, fallback_cap):
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    subjects, traces = {}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][i] for i in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = subjects.setdefault(subject, {'identity': identity, 'held': held, 'decisionsPerCase': 0,
                                               'counts': {name: Counter() for name in METHODS},
                                               'cases': {name: [0] * len(held) for name in METHODS}})
        if (group['identity'], group['held']) != (identity, held):
            raise ValueError('Paired models must align to the same held-out cases')
        group['decisionsPerCase'] += len(schedule['seeds'])
        trace = []
        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            nomination = RANKING.search_to_nomination(matrix, held, start, layouts, active, policy, fallback_cap)
            decisions = outcomes(matrix, held, start, layouts, active, policy, nomination)
            for method, decision in decisions.items():
                scores = [matrix[int(decision.prompt)][case] == '1' for case in held]
                group['cases'][method] = [a + b for a, b in zip(group['cases'][method], scores, strict=True)]
                group['counts'][method].update(
                    holdoutPasses=sum(scores), paidLookups=nomination.paid_search + decision.lookups,
                    proofLookups=decision.lookups, proofCapped=int(decision.status == 'undecided'),
                    promotions=int(decision.prompt != start), retries=int(decision.retry),
                    retryLookups=decision.retry_lookups, retryPromotions=int(decision.retry and decision.prompt != start))
            trace.append((seed, tuple((item.prompt, item.lookups, item.status, item.retry) for item in decisions.values())))
        traces[f'{subject}/{model}'] = digest(trace)
    return subjects, traces


def train(groups):
    proof = {key: {field: sum(item['counts'][key][field] for item in groups)
                   for field in ('promotions', 'proofLookups')} for key in METHODS}
    eligible = [method for method in METHODS if proof[method]['proofLookups'] <= proof[BASE]['proofLookups']]
    selected = min(eligible, key=lambda key: (-proof[key]['promotions'], proof[key]['proofLookups'], METHODS.index(key)))
    return {'admissionOnlyStats': proof, 'selected': selected}


def summarize(groups, plan, reference, native, selected):
    totals, ranges = {}, {}
    votes = {subject: {'cases': item['cases'], 'decisionsPerCase': item['decisionsPerCase']} for subject, item in groups.items()}
    for method in METHODS:
        totals[method] = sum((item['counts'][method] for item in groups.values()), Counter())
        if not method.startswith('retry/'):
            if any(totals[method][key] != reference['totals'][method][key] for key in (
                    'holdoutPasses', 'paidLookups', 'proofLookups', 'promotions', 'proofCapped')):
                raise ValueError('The full seeded or same-cap first-proof control changed')
        else:
            cap = method.rsplit('/', 1)[1]
            eligible = {arm: row for arm, row in native['totals'].items()
                        if row['paidLookups'] <= totals[method]['paidLookups'] and (
                            arm.startswith('gepa-') or arm == previous.previous.earlier.gap.paired.replay.START)}
            best = min(eligible, key=lambda arm: (-Fraction(eligible[arm]['macroAccuracy']), eligible[arm]['paidLookups'], arm))
            totals[method] = {**totals[method], 'bestAffordableNative': {'arm': best, **eligible[best]}}
            with patch.object(RANKING.paired_bands, 'BASELINE', f'expected-reads/{cap}'):
                ranges[method] = RANKING.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
    with patch.object(RANKING.paired_bands, 'BASELINE', 'expected-reads/24'):
        transfer = RANKING.paired_bands.paired_ranges(votes, selected, plan)['subjectsAndCases']
    return {'totals': totals, 'pairedVsSameCap': ranges, 'selectedOutsideFamily': selected,
            'selectedVsFullExpectedReads': transfer, 'qualifies': selected.startswith('retry/')
            and totals[selected]['paidLookups'] <= totals[BASE]['paidLookups']
            and transfer['interval95PercentagePoints'][0] > 0}


def execute(plan, reference, native, data):
    replayed = {phase: measure(*data[phase], plan['fallbackValidationCap']) for phase in RANKING.PHASES}
    bbh = RANKING.gap.paired.BBH
    training = {bbh: train(list(replayed[bbh][0].values())), 'mmlu': train(
        [unit for phase in RANKING.gap.paired.replay.PHASES for unit in replayed[phase][0].values()])}
    cohorts = {phase: {**summarize(groups, plan, reference['cohorts'][phase], native['cohorts'][phase],
                                   training['mmlu' if phase == bbh else bbh]['selected']), 'panelTraceSha256': traces}
               for phase, (groups, traces) in replayed.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'training': training,
            'cohorts': cohorts, 'qualifies': all(report['qualifies'] for report in cohorts.values())}


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
