"""Transfer the frozen public two-witness selector to archived AIME and ARC-AGI."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import pairwise
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_two_witness_pool_parity as parity
from cpo._contract import digest


model_transfer = parity.transfer
cost = model_transfer.cost
core = cost.transfer.study
math = core.math
PRIMARY = parity.screen.PAIRED
METHODS = (PRIMARY, core.FIRST, core.prior.CANDIDATE)
RETAIN = cost.frontier.RETAIN
HISTORICAL = 'historicalCostNanodollars'
MATH_REPORT = 'docs/recorded-first-training-certificate-results-v1.json'
MATH_SHA256 = 'ec23a9fba84c50f7a69bec6c0af41e68df674a5f3fd6425e8b2c5e1446fb7897'
PARITY_REPORT = 'docs/recorded-two-witness-pool-parity-results-v1.json'
PARITY_SHA256 = '8edd4b652562619d7db069724a1ee4c595ad4c2b8ef0d1d519e8a92695041c62'


def prepare():
    parent, data, _ = core.prepare()
    public, _ = parity.prepare()
    math_reference = cost.prior.baseline.read_reference(MATH_REPORT, MATH_SHA256, parent)
    cost.prior.baseline.read_reference(PARITY_REPORT, PARITY_SHA256, public)
    plan = {**{key: parent[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                            'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-two-witness-math-transfer-v1', 'mathPlanSha256': digest(parent),
            'mathReceiptSha256': MATH_SHA256, 'selectorPlanSha256': digest(public),
            'selectorReceiptSha256': PARITY_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'gepaModes': cost.MODES,
            'scope': 'Freeze the public selector and strict proof gates. Keep every original math split, '
                     'start, and roster size. Sweep integer GEPA search caps with the existing expected-cost '
                     'qualification. Compare at realized lookups and separately at ARC historical evaluator prices.'}
    return plan, data, math_reference['results']


def trials(cells, settings, group, width):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            eligible = [prompt for prompt in cells if prompt != start]
            yield start, Random(f'{seed}/{start}').sample(eligible, len(eligible))[:width], cohorts, seed


def matched(plan, totals, vectors, settings, accounting):
    priced = {label: {'holdoutPasses': row['holdoutPasses'], 'paidLookups': row[accounting]}
              for label, row in totals.items()}
    comparisons = cost.frontier.compare(priced, {'archived-cases': vectors}, policies=METHODS,
                                        draws=plan['bootstrapDraws'], seed=plan['bootstrapSeed'],
                                        groups={'either-mode': settings})
    result = {}
    for arm, entry in comparisons.items():
        row = entry['either-mode']
        row['bestWithinCostPoint'] = totals[row['bestWithinCost']]
        if row['cheapestMatching'] is not None:
            row['cheapestMatchingPoint'] = totals[row['cheapestMatching']]
        result[arm] = row
    return result


def measure(plan, cells, settings, group, width, reference):
    highest, lowest = plan['searchCap'], settings['cohorts'][1]
    metrics = (*cost.METRICS, HISTORICAL) if next(iter(cells.values()))[0][1] is not None else cost.METRICS
    labels = tuple(f'{mode}/{cap}' for mode in cost.MODES for cap in range(lowest, highest + 1))
    totals = {name: dict.fromkeys(metrics, 0) for name in (*METHODS, RETAIN, *labels)}
    vectors = {name: [0] * len(next(iter(cells.values()))) for name in totals}
    raw = {arm: Counter() for arm in (*METHODS, *cost.MODES)}
    traces = {arm: [] for arm in raw}
    trial_count = 0

    def add(name, point, grades, heldout):
        for key in metrics:
            totals[name][key] += point[key]
        for case, passed in zip(heldout, grades, strict=True):
            vectors[name][case] += passed

    for start, roster, cohorts, seed in trials(cells, settings, group, width):
        trial_count += 1
        heldout = cohorts[-1]
        args = (cells, start, roster, cohorts, seed)
        initial = [cells[start][case][0] for case in heldout]
        add(RETAIN, {'holdoutPasses': sum(initial), 'paidLookups': 0, HISTORICAL: 0}, initial, heldout)
        with patch.object(parity.shortlist, 'shortlist', parity.use_public):
            public = parity.shortlist.trial(*args, highest, PRIMARY)
        frozen = {arm: core.trial(*args, highest, arm) for arm in METHODS if arm != PRIMARY}
        for arm, (point, trace, grades) in {PRIMARY: public, **frozen}.items():
            raw[arm].update(point)
            traces[arm].append(trace)
            add(arm, point, grades, heldout)
        for mode in cost.MODES:
            paths = cost.budget_paths(args, mode, lowest, highest)
            full, trace, _ = paths[highest]
            raw[mode].update(full)
            traces[mode].append(trace)
            for lower, upper in pairwise((*paths, highest + 1)):
                point, _, grades = paths[lower]
                if point['searchLookups'] > lower or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']:
                    raise ValueError('A swept GEPA setting exceeded its allowance')
                for cap in range(lower, upper):
                    add(f'{mode}/{cap}', point, grades, heldout)

    anchors = {arm: {**point, 'traceSha256': digest(traces[arm])} for arm, point in raw.items()}
    if trial_count != reference['trialCount'] or any(anchors[arm] != reference['totals'][arm] for arm in anchors if arm != PRIMARY):
        raise ValueError('The published math controls and paid paths must reproduce before transfer')
    if any(sum(vectors[label]) != point['holdoutPasses'] for label, point in totals.items()):
        raise ValueError('The realized scores must match their by-case resampling vectors')
    comparison = {key: matched(plan, totals, vectors, labels, key) for key in metrics if key != 'holdoutPasses'}
    return {'trialCount': trial_count, 'totals': totals, 'anchors': anchors, 'comparisons': comparison}


def replay(plan, data, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {f'{group}/{width}': measure(cells=cells, plan=plan, settings=settings, group=group,
                                                       width=width, reference=reference[dataset][f'{group}/{width}'])
                            for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, data, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
