"""Bound the tested Promptolution controls when they can choose per episode in hindsight."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import language_roster_budget_frontier as frontier
from benchmarks import promptolution_settled_episode_transfer as transfer
from cpo._contract import digest


PARENT_SHA = '3458d801fa4f2bf94b38b01fad7934f1ecaa289cdb19fa0430468ac5fb422fab'
NATIVE, ALL = 'nativeGEPA', 'allControls'


def prepare():
    parent = transfer.locked('docs/promptolution-settled-episode-transfer-v1.json', PARENT_SHA)
    original = transfer.prepare()
    if digest(original) != parent['planSha256'] or digest(parent['plan']) != parent['planSha256']:
        raise ValueError('The original Promptolution transfer seal must reproduce')
    files = (Path(__file__).resolve(), Path(frontier.__file__).resolve(),
             transfer.donor.ROOT / 'benchmarks/recorded_math_roster_ceiling.py')
    plan = {'protocol': 'cpo-promptolution-settled-episode-headroom-v1',
            'parentReceiptSha256': PARENT_SHA, 'parentPlanSha256': parent['planSha256'],
            'corpusSha256': original['corpusSha256'], 'gepaVersion': original['gepaVersion'],
            'sourceSha256': {str(path.relative_to(transfer.donor.ROOT)): sha256(path.read_bytes()).hexdigest()
                             for path in files},
            'method': 'Allocate one tested setting per episode using realized lookup cost and final held-out passes. '
                      'Report the exact best score at each CPO lookup budget and minimum cost to match its score. '
                      'Report separate task ceilings, their sum under separate budgets, and the pooled ceiling.'}
    return plan, original, parent


def capture(original, archive, parent):
    methods = (*transfer.RUNNERS, transfer.BASE, *transfer.WITNESS, *original['controlSettings'])
    tasks = {}
    for task in original['tasks']:
        panel = archive[task]
        held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
        ))
        prior = parent['tasks'][task]
        if digest([panel['caseIDs'][case] for case in held]) != prior['heldCaseSha256']:
            raise ValueError('The original reserved holdout must reproduce')
        scores, traces = {method: Counter() for method in methods}, {method: [] for method in methods}
        episodes = []
        for seed in original['seeds']:
            windows = transfer.layout(original, task, seed, held)
            menu = {}
            for method in methods:
                winner, counts, trace = transfer.play(original, panel['correctness'], windows, seed, method)
                passed = sum(panel['correctness'][winner][case] == '1' for case in held)
                scores[method].update(counts, holdoutPasses=passed)
                traces[method].append(trace)
                menu[method] = frontier.Point(passed, counts['paidLookups'], (method,))
            episodes.append(menu)
        if {method: dict(scores[method], traceSha256=digest(traces[method])) for method in methods} != prior['arms']:
            raise ValueError('Every source arm must reproduce its paid trace, score, and cost')
        tasks[task] = episodes
    return tasks


def cost_frontier(menus):
    reachable = {0: 0}
    for menu in menus:
        reachable = frontier.extend(reachable, [(point.passes, point.cost) for point in frontier.efficient(menu)])
    return reachable


def witness(menus, budget):
    choices = frontier.pool(menus, budget)
    return {**frontier.summarize(choices),
            'settings': [point.actions[0] for point in choices]}


def evaluate(episodes, candidate, methods, original_comparison):
    actual = frontier.summarize([menu[candidate] for menu in episodes])
    budget, score = actual['paidLookups'], actual['holdoutPasses']
    menus = [tuple(episode[method] for method in methods) for episode in episodes]
    reachable = cost_frontier(menus)
    maximum = witness(menus, budget)
    expected = max(passes for passes, cost in reachable.items() if cost <= budget)
    if maximum['holdoutPasses'] != expected or maximum['paidLookups'] != reachable[expected]:
        raise ValueError('The best budgeted score must have an exact attainer at its minimum cost')
    fixed = None if original_comparison is None else original_comparison['controlPasses']
    if fixed is not None and maximum['holdoutPasses'] < fixed:
        raise ValueError('The episode menu includes the published fixed control')

    match = None
    prices = [cost for passes, cost in reachable.items() if passes >= score]
    if prices:
        price = min(prices)
        match = witness(menus, price)
        if match['holdoutPasses'] < score or match['paidLookups'] != price:
            raise ValueError('The minimum-cost score match must replay within its exact price')
    absolute = max(reachable)
    return {'candidate': actual, 'fixedControlPassesAtBudget': fixed, 'hindsightAtBudget': maximum,
            'unconstrainedHindsight': {'holdoutPasses': absolute, 'paidLookups': reachable[absolute]},
            'minimumCostToMatchCandidate': match, 'candidatePassesAboveHindsight': score - expected,
            'gainFromChoosingPerEpisode': None if fixed is None else expected - fixed,
            'frontierPointCount': len(reachable)}


def measure(plan, original, parent, archive):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA 0.1.4 environment')
    episodes = capture(original, archive, parent)
    families = {NATIVE: (transfer.BASE, *original['nativeMethods']),
                ALL: (transfer.BASE, *transfer.WITNESS, *original['controlSettings'])}

    def scope(menus, comparisons):
        return {candidate: {
            family: evaluate(menus, candidate, methods, comparisons[candidate][family])
            for family, methods in families.items()
        } for candidate in transfer.RUNNERS}

    per_task = {task: scope(menus, parent['tasks'][task]['comparisons']) for task, menus in episodes.items()}
    pooled = scope([menu for task in original['tasks'] for menu in episodes[task]], parent['pooledComparisons'])
    separate = {}
    for candidate in transfer.RUNNERS:
        separate[candidate] = {}
        for family in families:
            points = [task_result[candidate][family]['hindsightAtBudget'] for task_result in per_task.values()]
            separate[candidate][family] = {key: sum(point[key] for point in points)
                                           for key in ('holdoutPasses', 'paidLookups')}
            if separate[candidate][family]['holdoutPasses'] > pooled[candidate][family]['hindsightAtBudget']['holdoutPasses']:
                raise ValueError('A pooled budget must include the separate-budget allocation')
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'episodeOrderByTask': {task: original['seeds'] for task in original['tasks']},
            'tasks': per_task, 'pooled': pooled, 'pooledWithSeparateTaskBudgets': separate}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, parent = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if not args.corpus or args.execute != seal or not args.out or args.out.exists():
        parser.error('Replay requires its locked corpus, current seal, and a fresh output path')
    report = measure(plan, original, parent, transfer.donor.load_corpus(args.corpus.read_bytes()))
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
