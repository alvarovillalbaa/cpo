"""Transfer the fixed first-gain policies to three-cycle Promptolution episodes."""

import argparse
from bisect import bisect_right
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import certified_strict_gain as strict
from cpo._contract import digest


sweep = strict.sweep
archive, transfer = sweep.archive, sweep.transfer
STRICT_SHA = 'aaed69b26e4a8fce4a66377347bb36ac9e269acdd462f447f404fd116ce748dd'
PRIMARY = 'strict-gain/cap-18'
ARMS = (sweep.CANDIDATE, PRIMARY, 'strict-gain/cap-14')


def most_affordable_passes(budget, left, right):
    """Pick the best budget-feasible pair by score, then cost and arm order."""
    ordered = sorted((cost, name) for name, (_, cost) in right.items())
    thresholds, prefixes = [], []
    for cost, name in ordered:
        entry = -right[name][0], cost, name
        thresholds.append(cost)
        prefixes.append(min(prefixes[-1], entry) if prefixes else entry)

    choices = []
    for arm, (score, cost) in left.items():
        index = bisect_right(thresholds, budget - cost) - 1
        if index >= 0:
            neg_right, right_cost, second = prefixes[index]
            choices.append((-score + neg_right, cost + right_cost, arm, second))
    negative, cost, first, second = min(choices)
    return -negative, cost, (first, second)


def pooled_task_controls(plan, panels, candidate, methods):
    menus = [sweep.distinct_controls(methods, [(totals, vectors)]) for totals, vectors in panels]
    totals, vectors = zip(*panels, strict=True)
    costs = [{name: stats[name]['paidLookups'] for name in menu} for stats, menu in zip(totals, menus, strict=True)]
    budget = sum(stats[candidate]['paidLookups'] for stats in totals)
    candidate_passes = sum(sum(panel[candidate]) for panel in vectors)
    observed = [{name: (sum(panel[name]), prices[name]) for name in prices}
                for panel, prices in zip(vectors, costs, strict=True)]
    score, paid, arms = most_affordable_passes(budget, *observed)
    rng = Random(plan['resampleSeed'])
    samples, choices = [], Counter()
    for _ in range(plan['draws']):
        points = []
        trial_passes = 0
        for panel, prices in zip(vectors, costs, strict=True):
            width = len(panel[candidate])
            weights = Counter(rng.choices(range(width), k=width)).items()
            points.append({name: (sum(panel[name][index] * count for index, count in weights), cost)
                           for name, cost in prices.items()})
            trial_passes += sum(panel[candidate][index] * count for index, count in weights)
        trial_score, _, pair = most_affordable_passes(budget, *points)
        choices[' | '.join(pair)] += 1
        samples.append(trial_passes - trial_score)
    slots = len(plan['seeds']) * sum(len(panel[candidate]) for panel in vectors)
    return {'controlByTask': dict(zip(plan['tasks'], arms, strict=True)), 'candidateBudget': budget,
            'controlPaidLookups': paid, 'controlPasses': score, 'passDelta': candidate_passes - score,
            'resampledPairs': choices, **transfer.donor.ranges(samples, slots)}


def prepare():
    previous, *_ = strict.prepare()
    prior = transfer.locked('docs/certified-strict-gain-v1.json', STRICT_SHA)
    if digest(previous) != prior['planSha256'] or digest(prior['plan']) != prior['planSha256']:
        raise ValueError('The published math policy must reproduce its seal before transfer')
    baseline = transfer.locked('docs/certified-nomination-gepa-sweep-v1.json', strict.SWEEP_SHA)
    earlier = transfer.locked('docs/validation-routed-promptolution-v1.json', sweep.depth.width.PROMPTOLUTION_SHA)
    base, *_ = archive.prepare()
    file = Path(__file__)
    plan = {
        **base, 'protocol': 'cpo-certified-strict-gain-transfer-v1', 'primary': PRIMARY, 'arms': ARMS,
        'strictGainCaps': {arm: previous['strictGainCaps'][arm] for arm in ARMS[1:]},
        'sourceSha256': {**previous['sourceSha256'], **base['sourceSha256'],
                         str(file.relative_to(transfer.donor.ROOT)): sha256(file.read_bytes()).hexdigest()},
        'strictGainReceiptSha256': STRICT_SHA, 'sweepReceiptSha256': strict.SWEEP_SHA,
        'controlSettings': baseline['plan']['controlSettings'], 'nativeMethods': baseline['plan']['nativeMethods'],
        'scope': ('Transfer the 18- and 14-read first-gain policies to the original three-cycle Promptolution '
                  'episodes. Keep all original validation cases, qualification, held-out cases and control settings. '
                  'Require the old totals to reproduce. Track changes to finalists, deployments and cycle schedules. '
                  'Reselect the best affordable fixed control in every paired draw, including a distinct setting '
                  'per task under the pooled budget.'),
    }
    return plan, baseline['promptolution']['tasks'], earlier['tasks']


def verify_deployment(matrix, windows, decisions):
    incumbent = transfer.donor.START
    for (roster, _, _, proof), (_, nominee, deployed) in zip(windows, decisions, strict=True):
        if deployed != incumbent:
            if deployed != nominee or deployed not in roster:
                raise ValueError('A deployment left its enrolled roster or qualification nominee')
            gain = sum(int(matrix[deployed][row]) - int(matrix[incumbent][row]) for row in proof)
            if gain <= 0:
                raise ValueError('A deployment needs a strict gain on the independent qualification panel')
        incumbent = deployed


def compare(plan, panels):
    native = (*plan['nativeMethods'], transfer.BASE)
    overall = (*plan['controlSettings'], transfer.BASE)
    results = {}
    for arm in plan['arms']:
        controls = {
            label: transfer.compare(plan, panels, arm, sweep.distinct_controls(methods, panels))
            for label, methods in (('nativeGepa', native), ('includingHalving', overall))
        }
        if len(panels) == len(plan['tasks']):
            controls['pooledSettingsByTask'] = {
                label: pooled_task_controls(plan, panels, arm, methods)
                for label, methods in (('nativeGepa', native), ('includingHalving', overall))
            }
        if arm != sweep.CANDIDATE:
            controls['exactNominee'] = transfer.compare(plan, panels, arm, (sweep.CANDIDATE,), enforce_cap=False)
        results[arm] = controls
    return results


def measure(plan, task, panel, expected, earlier):
    methods = (*plan['arms'], transfer.BASE, *plan['controlSettings'])
    held = sorted(Random(f"{plan['holdoutSeed']}/{task}").sample(
        range(len(panel['caseIDs'])), transfer.donor.HOLDOUT))
    holdout_hash = digest([panel['caseIDs'][index] for index in held])
    if holdout_hash != earlier['heldCaseSha256']:
        raise ValueError('Use the original unmodified Promptolution holdout')
    totals = {arm: Counter() for arm in methods}
    vectors = {arm: [0] * len(held) for arm in methods}
    changes = {arm: Counter() for arm in plan['arms'][1:]}
    layouts = []
    matrix = panel['correctness']
    for seed in plan['seeds']:
        windows = transfer.layout(plan, task, seed, held)
        layouts.append((seed, windows))
        baseline = None
        for arm in methods:
            chosen, cost, trace = sweep.play(plan, matrix, windows, seed, arm)
            grades = [int(matrix[chosen][index]) for index in held]
            totals[arm].update(cost, holdoutPasses=sum(grades))
            vectors[arm] = [a + b for a, b in zip(vectors[arm], grades, strict=True)]
            if arm == sweep.CANDIDATE:
                baseline = trace[1]
            elif arm in changes:
                verify_deployment(matrix, windows, trace[1])
                changes[arm].update(changedFinalPrompt=int(chosen != baseline[-1][2]))
                for (old_schedule, old_nominee, old_deployed), (schedule, nominee, deployed) in zip(
                        baseline, trace[1], strict=True):
                    changes[arm].update(changedSchedule=int(schedule != old_schedule),
                                        changedNominee=int(nominee != old_nominee),
                                        changedDeployment=int(deployed != old_deployed))
    if len(layouts) != expected['episodes'] or any(totals[arm] != row for arm, row in expected['totals'].items()):
        raise ValueError('Every prior cost and holdout total must reproduce')
    point = totals, vectors
    return {'totals': totals, 'episodes': len(layouts), 'layoutSha256': digest(layouts),
            'heldCaseSha256': holdout_hash, 'changesFromExactNominee': changes,
            'comparisons': compare(plan, [point])}, point


def replay(plan, corpus, expected, earlier):
    methods = {sweep.CANDIDATE: partial(sweep.parity.packaged, True),
               **{arm: partial(strict.run, cap) for arm, cap in plan['strictGainCaps'].items()}}
    tasks, panels = {}, []
    with patch.dict(archive.RUNNERS, methods):
        for name in plan['tasks']:
            tasks[name], point = measure(plan, name, corpus[name], expected[name], earlier[name])
            panels.append(point)
    return {'tasks': tasks, 'pooledComparisons': compare(plan, panels)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, expected, earlier = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if (args.execute != seal or args.out is None or args.out.exists() or args.corpus is None
            or version('gepa') != plan['gepaVersion']):
        parser.error('Replay requires the pinned corpus, current seal, pinned GEPA and a fresh output path')
    corpus = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, **replay(plan, corpus, expected, earlier)}
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
