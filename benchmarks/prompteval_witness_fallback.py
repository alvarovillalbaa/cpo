"""Test the no-nominee fallback on the original BBH and LMentry protocol."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
import json
from unittest.mock import patch

from benchmarks import pool
from benchmarks import prompteval_narrow_native_admission as original
from benchmarks import prompteval_witness_tie_budget as paired
from cpo._contract import digest


REPLAY = original.REPLAY
ROOT = original.transfer.ROOT
BASE = original.CPO
FALLBACK = 'witness-then-halving'
HALVING = 'successive-halving/cap-8/one-admission'
ARMS = (BASE, FALLBACK, HALVING)
SOURCE = 'docs/prompteval-narrow-native-admission-results-v1.json'
SOURCE_SHA = '16e1dc37d6a088d2b4d6f1b3cb58e4153460490d10234ddb6c5c53fc49fd7092'


def prepare():
    prior, inputs, panels, _ = original.prepare()
    raw = (ROOT / SOURCE).read_bytes()
    receipt = json.loads(raw)
    if sha256(raw).hexdigest() != SOURCE_SHA or receipt['planSha256'] != digest(prior):
        raise ValueError('The published BBH and LMentry lookup frontier differs from its seal')
    path = Path(__file__).resolve()
    policy = ROOT / 'benchmarks/promptolution_witness_fallback.py'
    return {'protocol': 'prompteval-witness-no-nominee-fallback-transfer-v1', 'parentReportSha256': SOURCE_SHA,
            'parentPlanSha256': digest(prior), 'baseline': BASE, 'fallback': HALVING,
            'sourceSha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in (path, policy)},
            'pairedCaseDraws': prior['draws'], 'resamplingSeed': prior['seed'], 'admissionLimit': 1,
            'nativeReference': 'Reselect the best recorded fixed native setting affordable at each realized cost.',
            'gate': ('Transfer must have a strictly positive paired lower endpoint against the original witness '
                     'policy and a positive accuracy difference against the strongest affordable native setting.')}, inputs, panels, receipt


def play(matrix, held, starting, layouts, active, policy, select):
    nominated = False
    reads = {}

    def search(_method, incumbent, layout, observe, limits):
        nonlocal nominated
        if nominated:
            return incumbent

        def record(prompt, case):
            passed = observe(prompt, case)
            reads[prompt, case] = passed
            return passed

        nominee = select(incumbent, layout, record, limits)
        nominated = nominee != incumbent
        return nominee

    with patch.object(REPLAY, 'search', search):
        final, counts, trace = REPLAY.run_arm(matrix, held, starting, layouts, active, BASE, policy)
    proof = counts['qualificationLookups']
    if counts['paidLookups'] != len(reads) + proof or nominated != (proof > 0):
        raise ValueError('The one-admission replay failed to reconcile its exact purchases')
    return final, len(reads) + proof, trace, reads, proof


def witness(incumbent, layout, observe, limits):
    return original.transfer.select(original.matched.CPO, incumbent, layout, observe, limits)


def halving(incumbent, layout, observe, _limits):
    return pool.successive_halving((incumbent, *layout['alternatives']), layout['validation'], observe, 8)


def execute(plan, inputs, panels, receipt):
    schedule = inputs['schedule']
    active = {**schedule, 'evaluationLookupLimit': receipt['plan']['conditions'][BASE]['searchCap']}
    policy = inputs['qualificationBank']
    totals, subjects, results = {arm: Counter() for arm in ARMS}, {}, {}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        ids = [panel['caseIDs'][case] for case in held]
        unit = subjects.setdefault(subject, {'caseIds': ids, 'decisionsPerCase': 0,
                                             'cases': {arm: [0] * len(held) for arm in ARMS}})
        if unit['caseIds'] != ids:
            raise ValueError('Paired models must share holdout case identities')
        unit['decisionsPerCase'] += len(schedule['seeds'])
        counts, traces = {arm: Counter() for arm in ARMS}, []
        for seed in schedule['seeds']:
            starting, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            first = play(matrix, held, starting, layouts, active, policy, witness)
            reserve = play(matrix, held, starting, layouts, active, policy, halving)
            final, cost = first[:2]
            if not first[-1]:
                before, after = first[3], reserve[3]
                if any(before[key] != after[key] for key in before.keys() & after.keys()):
                    raise ValueError('Fallback lookup disagreed with a paid archived grade')
                final, cost = reserve[0], len(before.keys() | after.keys()) + reserve[-1]
                counts[FALLBACK].update(fallbacks=1, fallbackPromotions=int(final != starting),
                                        reusedLookups=len(before.keys() & after.keys()))
            choices = {BASE: first[:2], FALLBACK: (final, cost), HALVING: reserve[:2]}
            traces.append((seed, first[2], reserve[2], choices))
            for arm, (selected, paid) in choices.items():
                evaluations = [matrix[int(selected)][case] == '1' for case in held]
                counts[arm].update(holdoutPasses=sum(evaluations), paidLookups=paid)
                unit['cases'][arm] = [old + passed for old, passed in zip(unit['cases'][arm], evaluations, strict=True)]
        name = f'{subject}/{model}'
        if any(counts[BASE][key] != receipt['panels'][name][BASE][key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The published witness baseline changed on this panel')
        results[name] = {'arms': counts, 'traceSha256': digest(traces)}
        for arm in ARMS:
            totals[arm].update(counts[arm])
    accuracy = {arm: sum(Fraction(sum(group['cases'][arm]), len(group['caseIds']) * group['decisionsPerCase'])
                         for group in subjects.values()) / len(subjects) for arm in ARMS}
    with patch.object(paired, 'BASELINE', BASE):
        bands = paired.paired_ranges(subjects, FALLBACK, plan)
    eligible = {arm: stats for arm, stats in receipt['totals'].items()
                if arm.startswith('gepa-') and stats['paidLookups'] <= totals[FALLBACK]['paidLookups']}
    control, stats = min(eligible.items(), key=lambda item: (-Fraction(item[1]['macroAccuracy']),
                                                           item[1]['paidLookups'], item[0]))
    delta = accuracy[FALLBACK] - Fraction(stats['macroAccuracy'])
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'panels': results, 'totals': totals,
            'macroAccuracy': {arm: str(value) for arm, value in accuracy.items()}, 'versusOriginal': bands,
            'strongestAffordableNative': {'control': control, 'stats': stats, 'accuracyDelta': str(delta)},
            'qualifies': delta > 0 and all(row['interval95PercentagePoints'][0] > 0 for row in bands.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the published archive, current seal, and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
