"""Buy one matched validation case from the existing single-admission allowance."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_paid_nominee_ranking as earlier
from cpo._contract import digest


ROOT, REPLAY = earlier.ROOT, earlier.REPLAY
REFERENCE = 'docs/witness-paid-nominee-ranking-results-v1.json'
REFERENCE_SHA256 = 'ec3bc577da4b4348209949f7c3fcf036510a0f8cf4b05018fdb7cf4d9af2c12b'
CAPS = (16, 20, 24)
BASE = 'proof-only/24'
METHODS = {**{f'proof-only/{cap}': (cap, False) for cap in CAPS},
           **{f'paired-probe/{cap}': (cap, True) for cap in CAPS}}


class _ProofLimit(Exception):
    pass


def prepare():
    previous, native, data = earlier.prepare()
    raw = (ROOT / REFERENCE).read_bytes()
    archived = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or archived['planSha256'] != digest(previous):
        raise ValueError('Use the published nomination replay')
    plan = {'protocol': 'witness-nominee-paired-probe-v1', 'parentPlanSha256': digest(previous),
            'parentReportSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'fallbackValidationCap': previous['fallbackValidationCap'], 'caps': CAPS, 'maximumNewProbeGrades': 2,
            'pairedCaseDraws': previous['pairedCaseDraws'], 'resamplingSeed': previous['resamplingSeed'],
            'rule': 'Pick the strongest already-evaluated rival by smoothed paid pass rate. Compare with the '
                    'nominee on the cheapest enrolled case that can show a rival win. Charge it to the proof cap.',
            'fit': 'Choose cap and probe rule using other-family promotions and proof-plus-probe cost only.',
            'gate': 'Positive paired lower endpoint at no greater realized total cost than original on every cohort. '
                    'Probe credit also requires a positive lower endpoint against proof-only at its own cap.'}
    return plan, archived, native, data


def probe(nominee, paid, roster, evaluate):
    by_prompt = {}
    for (prompt, _), passed in paid.items():
        by_prompt.setdefault(prompt, Counter()).update(passes=passed, reads=1)
    rivals = [prompt for prompt in roster if prompt != nominee and prompt in by_prompt]
    if not rivals:
        return nominee, 0, False
    rival = max(rivals, key=lambda prompt: Fraction(by_prompt[prompt]['passes'] + 1, by_prompt[prompt]['reads'] + 2))
    shared = set(roster[rival]['validation'])
    best = None
    for case in roster[nominee]['validation']:
        if case not in shared:
            continue
        reference, challenger = paid.get((nominee, case)), paid.get((rival, case))
        if reference is True or challenger is False:
            continue
        cost = int(reference is None) + int(challenger is None)
        if best is None or cost < best[0]:
            best = cost, case, reference, challenger
    if best is None:
        return nominee, 0, False
    cost, case, reference, challenger = best
    if reference is None:
        reference = evaluate(nominee, case)
    if challenger is None:
        challenger = evaluate(rival, case)
    if type(reference) is not bool or type(challenger) is not bool:
        raise ValueError('A validation probe must return exact boolean grades')
    return rival if challenger and not reference else nominee, cost, True


def admit(start, nominee, current, bank, evaluate, *, plan, seed, recycle, remaining):
    calls = 0

    def read(prompt, case):
        nonlocal calls
        if calls == remaining:
            raise _ProofLimit
        calls += 1
        return evaluate(prompt, case)

    try:
        selected, _, receipt = REPLAY.qualify(start, nominee, current, bank, set(), read,
                                              plan=plan, seed=seed, recycle=recycle)
    except _ProofLimit:
        return start, calls, True
    if calls != receipt['qualificationLookups']:
        raise ValueError('The bounded proof disagrees with its ledger')
    return selected, calls, False


def outcomes(matrix, held, start, layouts, plan, policy, nomination):
    if nomination.original is None:
        return dict.fromkeys(METHODS, (start, 0, 0, False, False, False))
    roster = {prompt: layout for layout in layouts for prompt in layout['alternatives']}
    cycle_by_prompt = {prompt: index for index, layout in enumerate(layouts) for prompt in layout['alternatives']}
    blocked = set(held).union(*(layout['qualify'] for layout in layouts))
    if any(blocked.intersection(layout['validation']) for layout in layouts):
        raise ValueError('Probe choices must exclude every admission and held-out case')

    def grade(prompt, case):
        return matrix[int(prompt)][case] == '1'

    alternate, probe_cost, probed = probe(nomination.original, nomination.grades, roster, grade)
    proof_choices, decisions = {}, {}
    for method, (cap, enabled) in METHODS.items():
        nominee, cost = (alternate, probe_cost) if enabled else (nomination.original, 0)
        key = nominee, cap - cost
        layout = roster[nominee]
        if key not in proof_choices:
            cycle = cycle_by_prompt[nominee]
            bank = [case for previous in layouts[:cycle] for case in previous['qualify']]
            proof_choices[key] = admit(start, nominee, layout['qualify'], bank, grade, plan=plan, seed=layout['seed'],
                                       recycle=policy == 'recycle-unread', remaining=cap - cost)
        selected, proof, stopped = proof_choices[key]
        decisions[method] = selected, proof, cost, stopped, enabled and probed, nominee != nomination.original
    return decisions


def measure(inputs, panels, _native, _conditions, cap, fallback_cap):
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    subjects, traces = {}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][i] for i in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = subjects.setdefault(subject, {'identity': identity, 'held': held, 'decisionsPerCase': 0,
                                               'counts': {method: Counter() for method in METHODS},
                                               'cases': {method: [0] * len(held) for method in METHODS}})
        if (group['identity'], group['held']) != (identity, held):
            raise ValueError('Both recorded models must share the physical holdout')
        group['decisionsPerCase'] += len(schedule['seeds'])
        trace = []
        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            nomination = earlier.search_to_nomination(matrix, held, start, layouts, active, policy, fallback_cap)
            decisions = outcomes(matrix, held, start, layouts, active, policy, nomination)
            for method, (selected, proof, probe_cost, stopped, probed, switched) in decisions.items():
                if proof + probe_cost > METHODS[method][0]:
                    raise ValueError('The probe and proof exceeded their funded allowance')
                scores = [matrix[int(selected)][case] == '1' for case in held]
                group['cases'][method] = [a + b for a, b in zip(group['cases'][method], scores, strict=True)]
                group['counts'][method].update(holdoutPasses=sum(scores), paidLookups=nomination.paid_search + proof + probe_cost,
                                                proofLookups=proof, probeLookups=probe_cost, proofCapped=int(stopped),
                                                promotions=int(selected != start), pairedProbes=int(probed),
                                                changedNominees=int(switched))
            trace.append((seed, nomination.paid_search, decisions))
        traces[f'{subject}/{model}'] = digest(trace)
    return subjects, traces


def summarize_training(groups):
    fields = ('proofLookups', 'probeLookups', 'promotions')
    summary = {method: {field: sum(group['counts'][method][field] for group in groups) for field in fields}
               for method in METHODS}

    def cost(method):
        return summary[method]['proofLookups'] + summary[method]['probeLookups']

    order = (BASE, *(method for method in METHODS if method != BASE))
    eligible = [method for method in order if cost(method) <= cost(BASE)]
    selected = min(eligible, key=lambda method: (-summary[method]['promotions'], cost(method), order.index(method)))
    return {'admissionOnlyStats': summary, 'selected': selected}


def summarize(plan, groups, selected, reference, native):
    totals = {}
    for method in METHODS:
        stats = sum((unit['counts'][method] for unit in groups.values()), Counter())
        quality = sum(Fraction(sum(unit['cases'][method]), len(unit['held']) * unit['decisionsPerCase'])
                      for unit in groups.values()) / len(groups)
        affordable = {arm: row for arm, row in native['totals'].items()
                      if row['paidLookups'] <= stats['paidLookups'] and (
                          arm.startswith('gepa-') or arm == earlier.gap.paired.replay.START)}
        control = min(affordable, key=lambda arm: (-Fraction(affordable[arm]['macroAccuracy']),
                                                   affordable[arm]['paidLookups'], arm))
        totals[method] = {**stats, 'macroAccuracy': str(quality),
                          'affordableNativeOnObservedTotals': {'arm': control, **affordable[control]}}
    if any(totals[BASE][name] != reference['methods'][earlier.BASE][name] for name in
           ('holdoutPasses', 'paidLookups', 'proofLookups', 'promotions')):
        raise ValueError('The original full-proof control differs from its frozen replay')
    votes = {name: {'decisionsPerCase': unit['decisionsPerCase'], 'cases': unit['cases']} for name, unit in groups.items()}
    matching = f'proof-only/{METHODS[selected][0]}'
    bands = {}
    for method in METHODS:
        control = f'proof-only/{METHODS[method][0]}' if METHODS[method][1] else BASE
        with patch.object(earlier.paired_bands, 'BASELINE', control):
            bands[method] = earlier.paired_bands.paired_ranges(votes, method, plan)['subjectsAndCases']
    with patch.object(earlier.paired_bands, 'BASELINE', BASE):
        chosen_band = earlier.paired_bands.paired_ranges(votes, selected, plan)['subjectsAndCases']
    gate = totals[selected]['paidLookups'] <= totals[BASE]['paidLookups'] and chosen_band['interval95PercentagePoints'][0] > 0
    return {'totals': totals, 'selectedOutsideFamily': selected, 'pairedByMethod': bands,
            'selectedVsOriginal': chosen_band, 'selectedMatchedProofControl': matching,
            'qualifies': gate, 'probeQualifies': gate and METHODS[selected][1]
            and bands[selected]['interval95PercentagePoints'][0] > 0}


def execute(plan, archived, native, data):
    groups, traces = {}, {}
    for name in earlier.PHASES:
        groups[name], traces[name] = measure(*data[name], plan['fallbackValidationCap'])
    bbh = earlier.gap.paired.BBH
    training = {bbh: summarize_training(list(groups[bbh].values())), 'mmlu': summarize_training(
        [unit for name in earlier.gap.paired.replay.PHASES for unit in groups[name].values()])}
    results = {name: {**summarize(plan, groups[name], training['mmlu' if name == bbh else bbh]['selected'],
                                 archived['cohorts'][name], native['cohorts'][name]), 'panelTraceSha256': traces[name]}
               for name in earlier.PHASES}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'training': training, 'cohorts': results,
            'qualifies': all(row['qualifies'] for row in results.values())}


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
