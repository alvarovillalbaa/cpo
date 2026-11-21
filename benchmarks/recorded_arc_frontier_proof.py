"""Compare exact larger-pool parent proofs in archived ARC and the typed fixture."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import batched_field_feedback as batched
from benchmarks import recorded_arc_lineage_quotes as arc
from cpo._contract import digest


ARC_REFERENCE_SHA = '33b8bb87d8c3d6e44c4613adfcf459449726268d7319b99e313b1276da1f5582'
FIXTURE_REFERENCE_SHA = '6458708fa9f25c7b640344c6e94f76742a46d71e7ee73d66a569de0c90a06b56'
NATIVE = ('gepa-sequential-available-slots', 'gepa-batched-available-slots')
ORDINARY = arc.SKIP_EMPTY
ROW_ORDER = 'cpo-frontier-validation-order'
UNCERTAIN_FIRST = 'cpo-frontier-uncertain-first'
SETTLE_VALIDATION = 'cpo-frontier-settle-validation'
PROOF_ARMS = (ROW_ORDER, UNCERTAIN_FIRST, SETTLE_VALIDATION)
ARMS = (*NATIVE, ORDINARY, *PROOF_ARMS)


def load_reference(path, expected):
    raw = (arc.ROOT / 'docs' / path).read_bytes()
    if sha256(raw).hexdigest() != expected:
        raise ValueError('The published parent-proof comparison reference differs')
    return json.loads(raw)


def plan(cases):
    baseline = arc.availability_plan(cases, skip_empty_slots=True, matched_native=True)
    files = ('benchmarks/recorded_arc_frontier_proof.py', 'benchmarks/batched_field_feedback.py',
             'benchmarks/feedback_budget.py', 'benchmarks/sequential_field_feedback.py',
             'benchmarks/typed_policy.py', 'cpo/batched_field_rewrite.py', 'cpo/gepa_frontier.py')
    return {**baseline, 'protocol': 'cpo-recorded-arc-frontier-proof-v1', 'arms': ARMS,
            'arcReferenceSha256': ARC_REFERENCE_SHA, 'batchedFixtureReferenceSha256': FIXTURE_REFERENCE_SHA,
            'sourceSha256': {**baseline['sourceSha256'],
                             **{path: sha256((arc.ROOT / path).read_bytes()).hexdigest() for path in files}},
            'proof': 'Check every possible winner set permitted by the recorded paid grades. Compare validation-order '
                     'reads with cases sorted by the initial number of possible winner sets. In the settlement arm, '
                     'settle previously reserved validation grades when a new round exceeds the price ceiling.'}


def compare_arc(cases, scores, children, reference):
    quote = max(charge for rows in scores.values() for _, charge in rows.values())
    comparisons = {ORDINARY: NATIVE, ROW_ORDER: (ORDINARY, *NATIVE),
                   UNCERTAIN_FIRST: (ORDINARY, ROW_ORDER, *NATIVE),
                   SETTLE_VALIDATION: (ORDINARY, ROW_ORDER, *NATIVE)}
    points = {}
    for units in arc.QUOTE_UNITS:
        points[units] = {}
        for multiplier in arc.REFLECTION_QUOTES:
            paths, traces = [], []
            effects = {arm: Counter() for arm in PROOF_ARMS}
            for seed in arc.SEEDS:
                split = arc.split(cases, seed)
                for start, available in children.items():
                    if not available:
                        continue
                    rng = Random(f'{seed}/{start}')
                    orders = {parent: rng.sample(children, len(children)) for parent, children in children.items()}
                    args = start, split, scores, orders, seed, quote, quote * multiplier, units * quote
                    results = {mode: arc.play(mode.removesuffix('-available-slots'), *args, stop_on_exhaustion=True,
                                              native_reserve='available-slots') for mode in NATIVE}
                    schedules = {arm: [] for arm in (ORDINARY, *PROOF_ARMS)}
                    for arm, schedule in schedules.items():
                        results[arm] = arc.play('cpo-shared-budget', *args, stop_on_exhaustion=True, skip_empty_slots=True,
                                                frontier_bounds=arm != ORDINARY,
                                                prioritize_uncertain_cases=arm == UNCERTAIN_FIRST,
                                                settle_validation_on_price_limit=arm == SETTLE_VALIDATION,
                                                schedule_trace=schedule)
                    old, old_schedule = results[ORDINARY], schedules[ORDINARY]
                    for arm, counts in effects.items():
                        new, schedule = results[arm], schedules[arm]
                        if any(left != right for left, right in zip(old_schedule, schedule)):
                            raise ValueError('A certified ARC parent or minibatch changed within the common schedule')
                        counts.update(largePoolPaths=any(len(pool) >= 3 for pool, _, _ in schedule),
                                      scheduleExtensions=len(schedule) > len(old_schedule),
                                      scheduleShortenings=len(schedule) < len(old_schedule),
                                      changedNominees=new['nominee'] != old['nominee'],
                                      changedAdmissions=new['selected'] != old['selected'],
                                      moreSearchReads=new['searchReads'] > old['searchReads'],
                                      fewerSearchReads=new['searchReads'] < old['searchReads'],
                                      increasedRecordedCost=new['recordedEvaluationCostNanodollars'] >
                                                            old['recordedEvaluationCostNanodollars'])
                    paths.append((seed, start, results))
                    traces.append((seed, start, schedules))
            summary = arc.summarize(paths, arms=ARMS, comparisons=comparisons)
            previous = reference[str(units)][str(multiplier)]
            for arm in (*NATIVE, ORDINARY):
                if (summary['totals'][arm] != previous['totals'][arm] or any(
                        row[arm] != previous['byStart'][start][arm] for start, row in summary['byStart'].items())):
                    raise ValueError('The quoted ARC reference totals did not reproduce')
            points[units][multiplier] = {**summary, 'effects': effects, 'scheduleSha256': digest(traces)}
    return points


def compare_fixture(reference):
    ordinary = batched.measure(frontier_bounds=True)
    if json.loads(json.dumps(ordinary)) != reference:
        raise ValueError('The published batched fixture trace did not reproduce')
    original = batched.sequential_schedule

    def prioritize(*args, **options):
        return original(*args, **options, prioritize_uncertain_cases=True)

    with patch.object(batched, 'sequential_schedule', prioritize):
        updated = batched.measure(frontier_bounds=True)
    return {'validationOrder': ordinary['caps'], 'uncertainCasesFirst': updated['caps']}


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
        parser.error('Use the current seal, pinned GEPA 0.1.4, and a fresh output path')
    arc_reference = load_reference('recorded-arc-native-empty-slots-results-v1.json', ARC_REFERENCE_SHA)
    fixture = load_reference('batched-field-frontier-bounds-results-v1.json', FIXTURE_REFERENCE_SHA)
    result = {'plan': frozen, 'planSha256': seal,
              'arc': compare_arc(cases, scores, children, arc_reference['comparison']['points']),
              'scripted': compare_fixture(fixture), 'newProviderRequests': 0}
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
