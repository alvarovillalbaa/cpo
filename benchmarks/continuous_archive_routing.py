"""Replay three consecutive incumbent transitions on disjoint archived cases."""

import argparse
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass, replace
from functools import cache
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import short_circuit_archive_routing as previous
from benchmarks.validation_repair_anchor import attaining_trial
from cpo._contract import digest


transfer, routing = previous.transfer, previous.routing
native, RETAIN = transfer.native, transfer.RETAIN
STATIC, PRIMARY = previous.STATIC, previous.PRIMARY
COHORTS = previous.previous.COHORTS
CYCLES = 3
RECEIPTS = dict(zip(COHORTS, (
    '67384c3908861b12739d332f54e3334fd570193b4943080c45e4081f2af02995',
    'eeec37b6479da036bb2c51bf3c43cf69af13bd167faee768fb2d616b139a45ef',
    '9c78a3e0a8f187c9f5ba2f9536d2c8d48795eaeb616d3201089c97c3ab92560f',
    '0b2260abe5d1d394824541839ed7b7d9294a927fe8e9a2756dfb6df7359e7667',
    '4694d8622c72e1c2178ebcf2694c47d44e501bfa39453e53ec33e21fec7819ad',
    '33eb620ab15e8cbcda4f0c2d9d960efdf8cfa53699afa13c25d673ca824eb1f4',
    '0eb19894d73244208f51fbcbdf857968f0c975821847b9601c6aa6fe0f3e7a94',
), strict=True))


@dataclass(frozen=True)
class Span:
    """Settings in [lower, upper) with the same deployment and realized cost."""

    lower: int
    upper: int
    prompt: str
    paid: int = 0


def stages(subject, case_count, prompt_count, seed, plan):
    start, roster, first = transfer.layouts.schedule(subject, case_count, prompt_count, seed, plan)
    occupied = set().union(*first)
    held = first[-1]
    train, validation, proof = plan['caseCounts']
    cycle_width = train + validation + proof
    rest = Random(f'{seed}/{subject}/continuous-cases').sample(sorted(set(range(case_count)) - occupied),
                                                                  (plan['cycles'] - 1) * cycle_width)
    remaining = sorted(set(map(str, range(prompt_count))) - {start, *roster}, key=int)
    width = plan['challengers']
    prompts = Random(f'{seed}/{subject}/continuous-pool').sample(remaining, (plan['cycles'] - 1) * width)
    result = [(seed, roster, first)]
    for cycle in range(plan['cycles'] - 1):
        offset = cycle * cycle_width
        picked = rest[offset:offset + cycle_width]
        roles = picked[:train], picked[train:train + validation], picked[train + validation:], held
        result.append((seed + cycle + 1, prompts[cycle * width:(cycle + 1) * width], roles))
    return start, result


def extend_spans(spans, outcomes):
    """Propagate a fixed search cap through one cycle's sparse native thresholds."""
    result = []
    for span in spans:
        points = outcomes(span.prompt)
        boundaries = tuple(points)
        cursor = span.lower
        index = bisect_right(boundaries, cursor) - 1
        if index < 0:
            raise ValueError('Every reachable cap needs a measured native transition')
        while cursor < span.upper:
            point, trace, _ = points[boundaries[index]]
            stop = min(span.upper, boundaries[index + 1]) if index + 1 < len(boundaries) else span.upper
            item = Span(cursor, stop, trace[3], span.paid + point['paidLookups'])
            if (result and result[-1].upper == item.lower and result[-1].prompt == item.prompt
                    and result[-1].paid == item.paid):
                result[-1] = replace(result[-1], upper=item.upper)
            else:
                result.append(item)
            cursor, index = stop, index + 1
    return result


def native_episode(cells, start, cycles, high, first_changes, last_changes):
    held = cycles[0][2][-1]
    for mode in native.native.native_cost.MODES:
        for group, width in native.WIDTHS.items():
            @cache
            def paths(index, current):
                seed, roster, roles = cycles[index]
                args = native.validation_width((cells, current, roster, roles, seed), width)
                return native.gepa.native_paths(args, mode, width, high)

            first = paths(0, start)
            for rule, points in first.items():
                key = group, mode, rule
                native.native.record_boundaries(first_changes.setdefault(key, {}), points, high)
                spans = [Span(width, high + 1, start)]
                for index in range(len(cycles)):
                    spans = extend_spans(spans, lambda current: paths(index, current)[rule])
                deltas = last_changes.setdefault(key, {})
                for span in spans:
                    score = sum(cells[span.prompt][case][0] for case in held)
                    point = {'holdoutPasses': score, 'paidLookups': span.paid}
                    deltas.setdefault(span.lower, Counter()).update(point)
                    deltas.setdefault(span.upper, Counter()).subtract(point)
            paths.cache_clear()


def prepare(cohort):
    inherited, panels, models, static, _ = previous.prepare(cohort)
    name = f'docs/short-circuit-archive-routing-{cohort.lower()}-v1.json'
    receipt = json.loads(transfer.read_locked(name, RECEIPTS[cohort]))
    if receipt['planSha256'] != digest(inherited):
        raise ValueError('The first cycle must match the original single-cycle plan')
    plan = {**inherited, 'protocol': 'continuous-archive-routing-v1', 'cycles': CYCLES,
            'firstCycleReceiptSha256': RECEIPTS[cohort], 'sourceSha256': {
                **inherited['sourceSha256'], 'benchmarks/continuous_archive_routing.py':
                sha256(Path(__file__).read_bytes()).hexdigest()},
            'scope': 'Preserve the exact first cycle, then carry forward each policy’s deployed prompt on '
                     'two fresh role-disjoint case panels and fresh fixed proposal rosters. Measure final '
                     'holdout grades and all lookups. Each native setting uses the same engine, cap, width '
                     'and proof wrapper in every cycle. Reproduce the complete per-subject first-cycle '
                     'native grid and directly verify the final native attainers.'}
    return plan, panels, models, static, receipt['results']


def direct_comparison(panels, plan, vectors, schedules, expected):
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    points = {name: {} for name in schedules}
    for subject, _, matrix in panels:
        _, packed = transfer.case_cells(matrix)
        for seed in plan['seeds']:
            start, cycles = stages(subject, len(matrix[0]), len(matrix), seed, plan)
            for name, schedule in schedules.items():
                current, paid = start, 0
                for local_seed, roster, roles in cycles:
                    current, held, cost = attaining_trial(schedule[subject], (packed, current, roster, roles, local_seed))
                    paid += cost
                points[name].setdefault(subject, Counter()).update(holdoutPasses=sum(held), paidLookups=paid)
                add(vectors[subject].setdefault(name, [0] * len(held)), held)
    if points != expected:
        raise ValueError('Direct trajectory replays must attain every price and score selected from the native grid')
    paired = native.frozen.paired_effects.paired_effect
    return {name: paired(vectors, PRIMARY, name, plan) for name in (*schedules, STATIC)}


def measure(panels, plan, models, static, reference):
    _, compact = previous.make_runners(models, static)
    runners = {STATIC: routing.fitted_runner(STATIC, {STATIC: static}, Counter()), **compact}
    totals = {method: Counter() for method in runners}
    native_first, native_last, vectors, hashes = {}, {}, {}, {}
    run = native.paired.cycle.execute_path
    point = native.paired.reference.point
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    high = plan['searchCap']
    with native.split_safe_cache():
        for subject, model, matrix in panels:
            cells, packed = transfer.case_cells(matrix)
            first_points, last_points = native_first.setdefault(subject, {}), native_last.setdefault(subject, {})
            first_changes, last_changes = {}, {}
            first_paths, all_paths = ({method: [] for method in runners} for _ in range(2))
            for seed in plan['seeds']:
                start, cycles = stages(subject, len(matrix[0]), len(matrix), seed, plan)
                held = cycles[0][2][-1]
                initial = {'holdoutPasses': sum(cells[start][case] for case in held), 'paidLookups': 0}
                for native_points in (first_points, last_points):
                    native_points.setdefault(RETAIN, Counter()).update(initial)
                for name, runner in runners.items():
                    current, paid, promotions, trajectory = start, 0, 0, []
                    for local_seed, roster, roles in cycles:
                        result, ledger = run(runner, cells, current, roster, roles, local_seed, plan['fullRosterCap'], 1)
                        routing.verify_qualification(cells, current, roles, result, ledger, 1)
                        measured, grades, trace = point(cells, held, result, ledger)
                        trajectory.append((current, result.prompt, trace))
                        paid += measured['paidLookups']
                        promotions += int(result.promoted)
                        current = result.prompt
                    first_paths[name].append(trajectory[0][2])
                    all_paths[name].append(trajectory)
                    totals[name].update(holdoutPasses=sum(grades), paidLookups=paid, promotions=promotions,
                                        episodesWithPromotion=int(promotions > 0))
                    scores = vectors.setdefault(subject, {})
                    add(scores.setdefault(name, [0] * len(grades)), grades)
                native_episode(packed, start, cycles, high, first_changes, last_changes)
            transfer.tally_native(first_points, first_changes, high)
            transfer.tally_native(last_points, last_changes, high)
            panel = f'{subject}/{model}'
            if any(digest(path) != reference['panelPathHashes'][panel]['gain-1'][name]
                   for name, path in first_paths.items()):
                raise ValueError('All frozen CPO policies must reproduce their first-cycle traces')
            hashes[panel] = {method: digest(path) for method, path in all_paths.items()}

    if digest(native_first) != reference['nativeSubjectTotalsSha256']:
        raise ValueError('Every native first-cycle point must reproduce')
    settings = tuple(name for name in next(iter(native_last.values())) if name != RETAIN)
    common = {name: Counter() for name in (*settings, RETAIN)}
    for points in native_last.values():
        for name, measured in points.items():
            common[name].update(measured)
    budgets = {name: point['paidLookups'] for name, point in totals.items()}
    subject_ceiling = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    ceilings = subject_ceiling(native_last, settings, budgets)
    fixed = {name: native.gepa.best_fixed(common, settings, budget) for name, budget in budgets.items()}
    schedules = {'common-gepa': dict.fromkeys(native_last, fixed[PRIMARY]['setting']),
                 'subject-tuned-gepa': ceilings[PRIMARY]['settingsBySubject']}
    expected = {name: {subject: native_last[subject][setting] for subject, setting in schedule.items()}
                for name, schedule in schedules.items()}
    paired = direct_comparison(panels, plan, vectors, schedules, expected)
    passed = (paired['common-gepa']['pairedRange95'][0] > 0 and paired['subject-tuned-gepa']['holdoutPassDifference'] > 0
              and paired[STATIC]['pairedRange95'][0] > 0 and budgets[PRIMARY] <= budgets[STATIC])
    return {'cpo': totals, 'bestCommonGepa': fixed, 'subjectTunedGepa': ceilings, 'pairedPrimary': paired,
            'primaryGatePassed': passed, 'gepaSettings': len(settings), 'nativeFinalSubjectTotalsSha256': digest(native_last),
            'nativeFirstCycleSha256': digest(native_first), 'panelTrajectoryHashes': hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, models, static, reference = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh path and pinned GEPA')
    report = measure(panels, plan, models, static, reference)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': report}, out,
                  indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
