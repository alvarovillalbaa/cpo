"""Spend unspent search budget on archived candidates with exact critical validation."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_archive_restart as restart
from cpo import Observation, Row
from cpo._contract import digest
from cpo.challenger import certify_challenger


SEEDS = tuple(range(72601, 73513, 19))
PRIMARY = 'cpo-certified-eight'
SCREENS = {'cpo-full-eight': (8, False), 'cpo-certified-four': (4, True), PRIMARY: (8, True)}


def screen(incumbent, candidates, observations, validation, evaluate, *, metric_limit, candidate_limit, certified):
    """Screen unused archive entries in order and stop at the first certified gain."""
    exact = {row.id: observations[incumbent, row.id].passed for row in validation}
    if all(exact.values()):
        return incumbent, 0, []
    evaluations, attempts = 0, []
    for candidate in candidates[:candidate_limit]:
        remaining = metric_limit - evaluations
        cached = {row.id: observations[candidate, row.id].passed for row in validation
                  if (candidate, row.id) in observations}
        if certified:
            def probe(row):
                return evaluate(candidate, row)

            result = certify_challenger(validation, exact, probe, metric_limit=remaining, observed=cached)
            status, cost = result.status, result.evaluations
            if status == 'budget' and cost == 0:
                break
        else:
            fresh = [row for row in validation if row.id not in cached]
            if len(fresh) > remaining:
                break
            measured = {**cached, **{row.id: evaluate(candidate, row).passed for row in fresh}}

            def already_measured(_):
                raise ValueError('Full validation is already complete')

            status = certify_challenger(validation, exact, already_measured, metric_limit=0, observed=measured).status
            cost = len(fresh)
        evaluations += cost
        attempts.append({'prompt': candidate, 'status': status, 'evaluations': cost})
        if status == 'promote':
            return candidate, evaluations, attempts
    return incumbent, evaluations, attempts


def compare(data, seed, budget, run_gepa):
    (root, rows, matrix, original, _), graph, incumbent, _ = data
    order = sorted(rows)
    Random(seed).shuffle(order)
    train, validation, promotion, holdout = (order[start:start + 3] for start in (0, 3, 6, 9))
    ordering, earlier = restart.proposal_graph(graph, root, incumbent, seed, 'mixed')
    observations = {}
    original_search = restart.search

    def capture(initial, train_rows, validation_rows, evaluate, propose, **settings):
        def measured(prompt, row):
            value = evaluate(prompt, row)
            observations[prompt, row.id] = value
            return value

        return original_search(initial, train_rows, validation_rows, measured, propose, **settings)

    with patch.object(restart, 'search', capture):
        candidate, evaluations, proposals = restart.run_cpo(incumbent, rows, matrix, ordering, train, validation, seed, budget)
    if len(observations) != evaluations:
        raise ValueError('CPO prefix disagrees with paid search observations')
    arms = {}

    def record(arm, challenger, cost, slots, attempts=()):
        chosen, status, qualification, _ = restart.qualify(incumbent, challenger, rows, matrix, promotion)
        if cost > budget['metricLimit'] or len(slots) > budget['proposalSlots'] or qualification > 2 * len(promotion):
            raise ValueError('Replay exceeded its search or qualification cap')
        arms[arm] = {'challenger': challenger, 'chosen': chosen, 'promotion': status, 'searchEvaluations': cost,
                     'proposalSlots': len(slots), 'archiveLookups': sum(parent == incumbent and child in earlier
                                                                       for parent, child in slots),
                     'qualificationEvaluations': qualification, 'calls': cost + len(slots) + qualification,
                     'outcomes': {case: matrix[chosen][case][0] for case in holdout},
                     'originalHoldout': {case: outcome[0] for case, outcome in original.get(chosen, {}).items()},
                     'screen': attempts}

    record('cpo-mixed', candidate, evaluations, proposals)
    seen = {prompt for _, prompt in proposals}
    candidates = [prompt for prompt in ordering.get(incumbent, ()) if prompt in earlier and prompt not in seen]
    panel = [Row(case, 'task', rows[case]['critical']) for case in validation]
    for name, (limit, certified) in SCREENS.items():
        fresh = set()

        def evaluate(prompt, row):
            key = prompt, row.id
            if row.id not in validation or key in observations or key in fresh:
                raise ValueError('Replay asked for a nonvalidation or already paid observation')
            fresh.add(key)
            return Observation(matrix[prompt][row.id][0], {})

        selected, cost, attempts = screen(candidate, candidates, observations, panel, evaluate,
                                          metric_limit=budget['metricLimit'] - evaluations,
                                          candidate_limit=min(limit, budget['proposalSlots'] - len(proposals)),
                                          certified=certified)
        if cost != len(fresh):
            raise ValueError('Screen cost disagrees with the observation journal')
        slots = proposals + [(incumbent, item['prompt']) for item in attempts]
        record(name, selected, evaluations + cost, slots, attempts)

    for width, arm in enumerate(('gepa-sequential', 'gepa-batched'), 1):
        result = run_gepa(incumbent, train, validation, rows, matrix, ordering, seed, width=width, fields=True)
        steps = [(step['parent'], step['recordedChild']) for step in result['proposerSteps']]
        record(arm, result['selected'], result['searchCalls'], steps)
    return {'seed': seed, 'critical': [case for case in holdout if rows[case]['critical']], 'arms': arms}


def summarize(trials):
    with patch.object(restart, 'PRIMARY', PRIMARY):
        result = restart.summarize(trials)
    for arm in SCREENS:
        attempts = [item for trial in trials for item in trial['arms'][arm]['screen']]
        result['totals'][arm].update(screened=len(attempts), screenPromotions=sum(item['status'] == 'promote' for item in attempts),
                                     screenEvaluations=sum(item['evaluations'] for item in attempts))
    return result


def prepare():
    plan, data, run_gepa = restart.prepare()
    previous = digest(plan)
    path = Path(__file__)
    plan['sourceSha256']['benchmarks/recorded_archive_screen.py'] = sha256(path.read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-recorded-archive-screen-v1', 'restartPlanSha256': previous,
            'seeds': list(SEEDS), 'policies': list(SCREENS), 'primary': PRIMARY,
            'screenBudgets': {name: size for name, (size, _) in SCREENS.items()}}, data, run_gepa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, run_gepa = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {task: summarize([compare(inputs, seed, plan, run_gepa) for seed in plan['seeds']])
               for task, inputs in sorted(data.items())}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
