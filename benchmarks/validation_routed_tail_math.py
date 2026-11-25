"""Transfer the frozen stalled-tail policy to recorded AIME and ARC-AGI."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_two_witness_math_transfer as math
from benchmarks import validation_routed_tail as tail
from cpo._contract import digest


depth = tail.prior
archive, transfer, frontier = depth.prompt, depth.transfer, depth.width.frontier
STALLED = 'stalled-uniform-tail'
POLICIES = (depth.SETTLED, depth.ROUTED, 'uniform-depth-4', STALLED)
ARTIFACTS = {
    'docs/validation-routed-tail-v1.json': '2c426656fc00e48138f99ef40fa1518e4149aa0e7e8f32e0051c03296df3c613',
    'docs/recorded-math-validation-ties-results-v1.json': 'bf90d2fab3a9b33eece3a15392234db88afcaa13e5b8e2cf897ac54c9656e451',
}
WIDTH = 2
PRICE = 'historicalCostNanodollars'


def prepare():
    policy, *_ = tail.prepare()
    parent, corpus = math.math.prepare()
    controls, *_ = archive.prepare()
    for (path, lock), expected in zip(ARTIFACTS.items(), (policy, parent), strict=True):
        reference = transfer.locked(path, lock)
        if reference['planSha256'] != digest(expected) or digest(reference['plan']) != digest(expected):
            raise ValueError('Both the fixed policy and the original math splits must reproduce')
    root = math.math.ROOT
    paths = (Path(__file__), Path(math.__file__), Path(frontier.__file__),
             root / 'cpo/ordered_uniform_validation.py', root / 'cpo/bounded_uniform_validation.py')
    return {
        **{key: parent[key] for key in ('datasets', 'corpusSha256', 'incumbentGroups', 'gepaVersion',
                                      'bootstrapDraws', 'bootstrapSeed')},
        **{key: controls[key] for key in ('controlSettings', 'nativeMethods', 'validationPerCycle', 'admissionPerCycle')},
        'protocol': 'cpo-validation-routed-tail-math-v1', 'primary': STALLED, 'arms': POLICIES,
        'rosterWidth': WIDTH, 'parentReceipts': ARTIFACTS,
        'sourceSha256': {**parent['sourceSha256'], **policy['sourceSha256'],
                         **{str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in paths}},
        'scope': ('Transfer without refitting to the recorded math seeds, root and rotated starts, and holdouts. '
                  'Run one cycle per episode with the first two challengers in the same seeded roster order. '
                  'Use the first six original validation and first four reserved qualification cases for every arm. '
                  'Compare at actual lookups and at ARC historical evaluator charges. Keep the transferred native '
                  'GEPA and halving menu and reselect the best affordable control within each paired resample.'),
    }, corpus


def paired(plan, totals, vectors, peers):
    effects = depth.language.refit.native.frozen.paired_effects.paired_effect
    native = tuple(plan['nativeMethods'])
    simple = tuple(arm for arm in peers if arm not in native)
    comparisons = {arm: effects({'math': vectors}, STALLED, arm, plan) for arm in POLICIES if arm != STALLED}
    matched = {}
    for metric in ('paidLookups', PRICE):
        if metric not in totals[STALLED]:
            continue
        points = {arm: {**stats, 'paidLookups': stats[metric]} for arm, stats in totals.items()}
        matched[metric] = frontier.compare(
            points, {'math': vectors}, policies=(STALLED,), draws=plan['bootstrapDraws'], seed=plan['bootstrapSeed'],
            groups={'nativeGepa': native, 'halving': simple},
        )[STALLED]
        for comparison in matched[metric].values():
            winner = comparison['bestWithinCost']
            comparison['bestWithinCostPoint'] = totals[winner]
            match = comparison['cheapestMatching']
            if match is not None:
                comparison['cheapestMatchingPoint'] = totals[match]
    return comparisons, matched


def measure(plan, cells, settings, group):
    peers = tuple(plan['controlSettings'])
    arms = (*POLICIES, *peers, transfer.BASE)
    priced = next(iter(cells.values()))[0][1] is not None
    totals = {arm: Counter({PRICE: 0} if priced else {}) for arm in arms}
    vectors = {arm: [0] * len(next(iter(cells.values()))) for arm in arms}
    schedules = {arm: Counter() for arm in POLICIES}
    matrix = {prompt: ''.join(str(int(cell[0])) for cell in rows) for prompt, rows in cells.items()}
    layout = []
    for start, roster, (training, validation, qualification, held), seed in math.trials(cells, settings, group, WIDTH):
        validation = validation[:plan['validationPerCycle']]
        proof = qualification[:plan['admissionPerCycle']]
        windows = [(tuple(roster), tuple(training), tuple(validation), tuple(proof))]
        layout.append((start, windows, held, seed))
        with patch.object(transfer.donor, 'START', start):
            for arm in arms:
                chosen, cost, (_, decisions, ledger) = archive.play(plan, matrix, windows, seed, arm)
                if chosen != start and sum(cells[chosen][case][0] - cells[start][case][0] for case in proof) < 1:
                    raise ValueError('Every deployed change must improve on independent qualification')
                for case in held:
                    vectors[arm][case] += cells[chosen][case][0]
                totals[arm].update(cost, holdoutPasses=sum(cells[chosen][case][0] for case in held),
                                   promotions=int(chosen != start))
                if priced:
                    totals[arm][PRICE] += sum(cells[prompt][case][1] for (_, prompt, case), _ in ledger)
                if arm in POLICIES:
                    schedules[arm][decisions[0][0]] += 1
    direct, matched = paired(plan, totals, vectors, peers)
    return {'episodes': len(layout), 'layoutSha256': digest(layout), 'totals': totals, 'schedules': schedules,
            'paired': direct, 'matched': matched}


def replay(plan, corpus):
    with patch.dict(archive.RUNNERS, {arm: tail.RUNNERS[arm] for arm in POLICIES}):
        return {
            subject: {group: measure(plan, math.math.load_cells(subject, corpus[subject]['record']), settings, group)
                      for group in plan['incumbentGroups']}
            for subject, settings in plan['datasets'].items()
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, corpus = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, corpus)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
