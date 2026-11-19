"""Replay continuous prompt search with and without access to earlier proposal branches."""

import argparse
from collections import deque
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from cpo import Observation, ProposalBatch, Row, search
from cpo._contract import digest
from cpo.challenger import certify_challenger


SEEDS = tuple(range(70501, 71413, 19))
POLICIES = ('descendants', 'local-first', 'mixed')
SEARCHES = ('cpo', 'gepa-sequential', 'gepa-batched')
PRIMARY = 'cpo.mixed'


def reachable(graph, initial):
    visited = {initial}
    pending = [initial]
    while pending:
        parent = pending.pop()
        for child in graph.get(parent, ()):
            if child not in visited:
                visited.add(child)
                pending.append(child)
    return visited


def proposal_graph(graph, root, incumbent, seed, policy):
    generator = Random(seed)
    ordered = {parent: generator.sample(children, len(children)) for parent, children in sorted(graph.items())}
    earlier = sorted(reachable(graph, root) - reachable(graph, incumbent) - {root})
    if policy != 'descendants' and earlier:
        local = ordered.get(incumbent, [])
        alternatives = generator.sample(earlier, len(earlier))
        combined = local + alternatives
        ordered[incumbent] = combined if policy == 'local-first' else generator.sample(combined, len(combined))
    return ordered, set(earlier)


def run_cpo(incumbent, rows, matrix, graph, train, validation, seed, budget):
    paid = set()
    proposals = []
    queues = {parent: deque(children) for parent, children in graph.items()}
    allowed = set(train + validation)

    def evaluate(prompt, row):
        key = prompt, row.id
        if row.id not in allowed or key in paid or len(paid) >= budget['metricLimit']:
            raise ValueError('CPO attempted an unavailable or over-budget search observation')
        paid.add(key)
        exact, fields = matrix[prompt][row.id]
        return Observation(exact, {}, fields)

    def propose(parent, _feedback, _history, width):
        queue = queues.get(parent)
        requested = tuple(queue.popleft() for _ in range(min(width, len(queue or ()))))
        slots = requested + (None,) * (width - len(requested))
        proposals.extend((parent, child) for child in slots)
        return ProposalBatch(requested, exhausted=not queue)

    def cohort(cases):
        return [Row(case, 'task', rows[case]['critical'], len(rows[case]['expected'])) for case in cases]

    result = search(incumbent, cohort(train), cohort(validation), evaluate, propose,
                    metric_limit=budget['metricLimit'], rounds=budget['proposalSlots'] // 2,
                    train_per_round=budget['trainPerRound'], seed=seed, adaptive=True, field_credit=True)
    if len(proposals) > budget['proposalSlots'] or result.evaluations != len(paid):
        raise ValueError('CPO disagrees with archived replay accounting')
    return result.prompt, result.evaluations, proposals


def qualify(incumbent, candidate, metadata, matrix, qualification):
    if candidate == incumbent:
        return incumbent, 'unchanged', 0, {}
    rows = [Row(case, 'task', metadata[case]['critical']) for case in qualification]
    base = {case: matrix[incumbent][case][0] for case in qualification}
    result = certify_challenger(rows, base, lambda row: Observation(matrix[candidate][row.id][0], {}),
                               metric_limit=len(rows))
    selected = candidate if result.status == 'promote' else incumbent
    return selected, result.status, len(rows) + result.evaluations, result.observations


def compare(data, seed, budget, run_gepa):
    (root, rows, matrix, original, _), graph, incumbent, _ = data
    order = sorted(rows)
    Random(seed).shuffle(order)
    train, validation, promotion, holdout = (order[start:start + 3] for start in (0, 3, 6, 9))
    arms = {}
    for policy in POLICIES:
        candidate_graph, earlier = proposal_graph(graph, root, incumbent, seed, policy)
        contestants = {'cpo': run_cpo(incumbent, rows, matrix, candidate_graph, train, validation, seed, budget)}
        for width, algorithm in enumerate(SEARCHES[1:], 1):
            value = run_gepa(incumbent, train, validation, rows, matrix, candidate_graph, seed, width=width, fields=True)
            proposals = [(step['parent'], step['recordedChild']) for step in value['proposerSteps']]
            contestants[algorithm] = value['selected'], value['searchCalls'], proposals

        for algorithm, (candidate, evaluations, proposals) in contestants.items():
            chosen, status, qualification_calls, receipt = qualify(incumbent, candidate, rows, matrix, promotion)
            lookups = sum(parent == incumbent and child in earlier for parent, child in proposals)
            arms[f'{algorithm}.{policy}'] = {
                'challenger': candidate, 'chosen': chosen, 'promotion': status, 'qualification': receipt,
                'searchEvaluations': evaluations, 'proposalSlots': len(proposals), 'archiveLookups': lookups,
                'qualificationEvaluations': qualification_calls, 'calls': evaluations + len(proposals) + qualification_calls,
                'proposalSha256': digest(proposals), 'outcomes': {case: matrix[chosen][case][0] for case in holdout},
                'originalHoldout': {case: outcome[0] for case, outcome in original[chosen].items()} if chosen in original else {},
            }
    return {'seed': seed, 'critical': [case for case in holdout if rows[case]['critical']], 'arms': arms}


def summarize(trials):
    totals, comparisons = {}, {}
    for arm in trials[0]['arms']:
        entries = [trial['arms'][arm] for trial in trials]
        totals[arm] = {key: sum(row[key] for row in entries) for key in ('calls', 'archiveLookups', 'qualificationEvaluations')}
        totals[arm]['passes'] = sum(sum(row['outcomes'].values()) for row in entries)
        totals[arm]['promotions'] = sum(row['promotion'] == 'promote' for row in entries)
        if arm == PRIMARY:
            continue

        delta = critical = saved = original_pairs = original_delta = original_cases = 0
        for trial in trials:
            candidate, reference = (trial['arms'][method] for method in (PRIMARY, arm))
            delta += sum(candidate['outcomes'].values()) - sum(reference['outcomes'].values())
            critical += sum(reference['outcomes'][case] and not candidate['outcomes'][case] for case in trial['critical'])
            saved += reference['calls'] - candidate['calls']
            a, b = candidate['originalHoldout'], reference['originalHoldout']
            shared = a.keys() & b.keys()
            original_pairs += bool(shared)
            original_cases += len(shared)
            original_delta += sum(int(a[case]) - b[case] for case in shared)
        comparisons[arm] = {'passDelta': delta, 'criticalLosses': critical, 'callsSaved': saved,
                            'matchedOriginalHoldoutTrials': original_pairs, 'matchedOriginalHoldoutCases': original_cases,
                            'originalHoldoutPassDelta': original_delta}
    for arm, outcome in comparisons.items():
        gain, saved, losses = (outcome[key] for key in ('passDelta', 'callsSaved', 'criticalLosses'))
        outcome['qualified'] = not losses and saved >= 0 and (gain > 0 or gain == 0 and 10 * saved >= totals[arm]['calls'])
    return {'totals': totals, 'comparisons': comparisons, 'trials': trials}


def coverage(data):
    (root, rows, matrix, _, _), graph, incumbent, _ = data
    passed = {prompt: {case for case, outcome in scores.items() if outcome[0]} for prompt, scores in matrix.items()}
    base = passed[incumbent]
    critical = {case for case in base if rows[case]['critical']}
    better = {prompt for prompt, hits in passed.items() if len(hits) > len(base) and critical <= hits}
    current = reachable(graph, incumbent)
    return {'incumbentPasses': len(base), 'descendants': len(current) - 1,
            'improvingDescendants': len(better & current),
            'improvingEarlierBranches': len(better & (reachable(graph, root) - current))}


def prepare():
    import cpo_recorded_opening_pair as archive

    archived, data = archive.plan()
    root = Path(__file__).resolve().parents[1]
    paths = ('benchmarks/recorded_archive_restart.py', 'cpo/optimizer.py', 'cpo/challenger.py', 'cpo/_contract.py')
    plan = {'protocol': 'cpo-recorded-archive-restart-v1', 'delivery': 'recorded-outcome-replay',
            'archivePlanSha256': digest(archived), 'sourcePlanSha256': archived['sourcePlanSha256'],
            'gepaVersion': archived['gepaVersion'], 'seeds': list(SEEDS), 'policies': list(POLICIES), 'primary': PRIMARY,
            'cohortSizes': [3, 3, 3, 3], 'incumbent': 'original recorded opening rewrite',
            **{key: archived[key] for key in ('metricLimit', 'proposalSlots', 'trainPerRound')},
            'sourceSha256': {file: sha256((root / file).read_bytes()).hexdigest() for file in paths}}
    return plan, data, archive.lineage.run_gepa


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
    results = {task: {**summarize([compare(inputs, seed, plan, run_gepa) for seed in plan['seeds']]),
                      'coverage': coverage(inputs)} for task, inputs in sorted(data.items())}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
