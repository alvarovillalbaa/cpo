"""Measure adaptive validation ordering with exact GEPA parent certificates."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import batched_field_feedback as batched, gepa_sequential_schedule as schedule
from benchmarks import recorded_arc_frontier_proof as prior, recorded_arc_lineage_quotes as arc
from cpo._contract import digest


REFERENCE = 'recorded-arc-frontier-proof-results-v1.json'
REFERENCE_SHA = '742061eb5c3d341fe1090549aa5aa33fad6bb59e58ae4af7c9288314d8c112d1'
CONTROL = prior.SETTLE_VALIDATION
ADAPTIVE = 'cpo-frontier-adaptive-case-order'


def plan(cases):
    inherited = prior.plan(cases)
    return {**inherited, 'protocol': 'cpo-recorded-arc-adaptive-case-order-v1', 'arms': (CONTROL, ADAPTIVE),
            'parentResultSha256': REFERENCE_SHA, 'sourceSha256': {
                **inherited['sourceSha256'], 'benchmarks/recorded_arc_adaptive_case_order.py':
                sha256((arc.ROOT / 'benchmarks/recorded_arc_adaptive_case_order.py').read_bytes()).hexdigest(),
            }, 'proof': 'After every paid read, rank unread cases by the remaining count of possible winner sets. '
                        'Use validation and candidate order for ties. Preserve the exact parent certificate.'}


def measure_arc(cases, scores, children, reference):
    quote = max(charge for rows in scores.values() for _, charge in rows.values())
    prioritize = partial(schedule.sequential_schedule, adaptive_case_order=True)
    results = {}
    for units in arc.QUOTE_UNITS:
        results[units] = {}
        for multiplier in arc.REFLECTION_QUOTES:
            paths, traces, effects = [], [], Counter()
            for seed in arc.SEEDS:
                split = arc.split(cases, seed)
                for start, available in children.items():
                    if not available:
                        continue
                    rng = Random(f'{seed}/{start}')
                    orders = {parent: rng.sample(items, len(items)) for parent, items in children.items()}
                    args = start, split, scores, orders, seed, quote, quote * multiplier, units * quote
                    traces_before, traces_after = [], []
                    settings = {'stop_on_exhaustion': True, 'skip_empty_slots': True, 'frontier_bounds': True,
                                'settle_validation_on_price_limit': True}
                    before = arc.play('cpo-shared-budget', *args, **settings, schedule_trace=traces_before)
                    with patch.object(schedule, 'sequential_schedule', prioritize):
                        after = arc.play('cpo-shared-budget', *args, **settings, schedule_trace=traces_after)
                    if traces_before != traces_after or any(before[key] != after[key]
                                                            for key in ('nominee', 'selected', 'passes')):
                        raise ValueError('Adaptive case ordering changed a recorded ARC decision')
                    effects.update(fewerReads=after['searchReads'] < before['searchReads'],
                                   moreReads=after['searchReads'] > before['searchReads'],
                                   moreEvaluationCost=after['recordedEvaluationCostNanodollars'] >
                                   before['recordedEvaluationCostNanodollars'])
                    paths.append((seed, start, {CONTROL: before, ADAPTIVE: after}))
                    traces.append((seed, start, traces_after))
            summary = arc.summarize(paths, arms=(CONTROL, ADAPTIVE), comparisons={ADAPTIVE: (CONTROL,)})
            expected = reference[str(units)][str(multiplier)]
            if (summary['totals'][CONTROL] != expected['totals'][CONTROL] or any(
                    row[CONTROL] != expected['byStart'][start][CONTROL] for start, row in summary['byStart'].items())):
                raise ValueError('The previously published settlement arm changed')
            results[units][multiplier] = {**summary, 'effects': effects, 'scheduleSha256': digest(traces)}
    return results


def measure_fixture(reference):
    ordinary = batched.measure(frontier_bounds=True)['caps']
    if json.loads(json.dumps(ordinary)) != reference['validationOrder']:
        raise ValueError('The published width-two fixture reference changed')
    with patch.object(batched, 'sequential_schedule', partial(batched.sequential_schedule, adaptive_case_order=True)):
        adaptive = batched.measure(frontier_bounds=True)['caps']
    return {'validationOrder': ordinary, 'adaptiveCaseOrder': adaptive,
            'priorUncertainCasesFirst': reference['uncertainCasesFirst']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    cases, scores, children = arc.load_archive()
    frozen = plan(cases)
    seal = digest(frozen)
    if args.execute is None and args.out is None:
        print(json.dumps({**frozen, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != '0.1.4':
        parser.error('Use the current seal, pinned GEPA 0.1.4, and a fresh receipt path')
    reference = prior.load_reference(REFERENCE, REFERENCE_SHA)
    result = {'plan': frozen, 'planSha256': seal, 'arc': measure_arc(cases, scores, children, reference['arc']),
              'scripted': measure_fixture(reference['scripted']), 'newProviderRequests': 0}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
