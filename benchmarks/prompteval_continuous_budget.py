"""Replay early search stopping and incumbent-dependent lookup budgets."""

import argparse
from hashlib import sha256
from importlib.metadata import version
from inspect import signature
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_continuous as continuous
from cpo import cycle, optimizer
from cpo._contract import digest


PRIMARY = 'cpo-incumbent-budget'
POLICIES = ('cpo-rank-only', 'cpo-early-stop', 'cpo-fixed-96', 'cpo-fixed-112', PRIMARY)
CONTROLS = ('cpo-cycle', *continuous.GEPA)
ARMS = (*CONTROLS, *POLICIES)


def prepare(phase):
    base, data = continuous.prepare(phase)
    root = Path(__file__).resolve().parents[1]
    files = (Path(__file__), root / 'benchmarks/patches/continuous-budget-policy.patch')
    source_hashes = {file.relative_to(root).as_posix(): sha256(file.read_bytes()).hexdigest() for file in files}
    return {**base, 'protocol': 'prompteval-continuous-budget-policy-v1', 'arms': list(ARMS),
            'primary': PRIMARY, 'controls': list(CONTROLS), 'fixedCaps': {'cpo-fixed-96': 96, 'cpo-fixed-112': 112},
            'targetGain': 2, 'stallRounds': 2, 'incumbentPassFraction': [3, 4],
            'incumbentCaps': {'high': 64, 'low': 112},
            'sourceSha256': {**base['sourceSha256'], **source_hashes}}, data


def configure_search(arm, plan, record):
    def policy(initial, train, validation, evaluate, propose, **settings):
        options = {'leader_only': True}
        if arm != 'cpo-rank-only':
            options.update(gain_target=plan['targetGain'], idle_limit=plan['stallRounds'])
        cap = min(settings['metric_limit'], plan['fixedCaps'].get(arm, settings['metric_limit']))
        if arm == PRIMARY:
            known = {row.id: evaluate(initial, row) for row in validation}
            pass_count = sum(result.passed for result in known.values())
            numerator, denominator = plan['incumbentPassFraction']
            tier = 'high' if pass_count * denominator >= len(validation) * numerator else 'low'
            cap = min(cap, plan['incumbentCaps'][tier])
            record['incumbentPasses'] = pass_count

            def evaluate_with_cache(prompt, row):
                if prompt == initial and row.id in known:
                    return known[row.id]
                return evaluate(prompt, row)
        else:
            evaluate_with_cache = evaluate
        record['searchCap'] = cap
        return optimizer.search(initial, train, validation, evaluate_with_cache, propose,
                                **{**settings, 'metric_limit': cap}, **options)
    return policy


def simulate(matrix, holdout, seed, plan):
    initial, layouts = continuous.schedule(len(matrix[0]), len(matrix), holdout, seed, plan)
    results = {}
    for arm in ARMS:
        incumbent = initial
        steps = []
        for layout in layouts:
            if arm in POLICIES:
                budget = {}
                with patch.object(cycle, 'search', configure_search(arm, plan, budget)):
                    result = continuous.step('cpo-cycle', matrix, incumbent, layout, plan)
                if result['searchLookups'] > budget['searchCap']:
                    raise ValueError('Search exceeded the selected cap')
                result.update(budget)
            else:
                result = continuous.step(arm, matrix, incumbent, layout, plan)
            incumbent = result['selected']
            steps.append(result)
        results[arm] = {'candidate': incumbent, 'steps': steps,
                        'holdoutPasses': sum(matrix[int(incumbent)][row] == '1' for row in holdout)}
    return {'seed': seed, 'initial': initial, 'layouts': layouts, 'arms': results}


def summarize(episodes):
    totals = {}
    for arm in ARMS:
        results = [episode['arms'][arm] for episode in episodes]
        steps = [step for result in results for step in result['steps']]
        totals[arm] = {'holdoutPasses': sum(result['holdoutPasses'] for result in results),
                       'searchLookups': sum(step['searchLookups'] for step in steps),
                       'qualificationLookups': sum(step['qualificationLookups'] for step in steps),
                       'promotions': sum(step['incumbent'] != step['selected'] for step in steps)}
    comparisons = {}
    for arm in POLICIES:
        comparisons[arm] = {}
        for control in CONTROLS:
            candidate, baseline = (totals[name] for name in (arm, control))
            cost, reference = (row['searchLookups'] + row['qualificationLookups'] for row in (candidate, baseline))
            gain = candidate['holdoutPasses'] - baseline['holdoutPasses']
            comparisons[arm][control] = {'passDelta': gain, 'lookupDelta': cost - reference,
                                         'qualified': gain >= 0 and cost <= reference and
                                                      (gain > 0 or 10 * cost <= 9 * reference)}
    return {'totals': totals, 'comparisons': comparisons}


def execute(plan, source):
    if version('gepa') != plan['gepaVersion'] or 'leader_only' not in signature(optimizer.search).parameters:
        raise ValueError('Use pinned GEPA and the continuous-budget-policy prototype patch')
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        holdout = plan['holdoutCaseIDs'][subject]
        episodes = [simulate(matrix, holdout, seed, plan) for seed in plan['seeds']]
        panels[f'{subject}/{model}'] = {**summarize(episodes), 'episodes': episodes}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('development', 'retrospective-transfer'), required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    result = execute(plan, data)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
