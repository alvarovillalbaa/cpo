"""Replay critical-case allocation across every three-row recorded holdout."""

import argparse
from hashlib import sha256
from importlib.metadata import version
from itertools import combinations
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_archive_restart as restart, recorded_archive_screen as screened
from cpo import Observation, Row
from cpo._contract import digest


SEED_START = 78031
POLICIES = {'shuffled': 0, 'one-critical': 1, 'two-critical': 2}
METHODS = ('cpo', 'gepa-sequential', 'gepa-batched')
PRIMARY = 'cpo.two-critical'


def assign_panels(validation, promotion, metadata, minimum):
    """Move only as many rows as needed to allocate critical cases to both roles."""
    validation, promotion = list(validation), list(promotion)
    if not minimum:
        return validation, promotion
    critical = {case for case in validation + promotion if metadata[case]['critical']}
    reserve = int(len(critical) >= 2)
    high = min(len(promotion), len(critical) - reserve)
    low = min(minimum, high)
    existing = len(critical.intersection(promotion))
    target = min(max(existing, low), high)
    increase = target > existing
    validation_slots = [idx for idx, case in enumerate(validation) if (case in critical) == increase]
    promotion_slots = [idx for idx, case in enumerate(promotion) if (case in critical) != increase]
    swaps = abs(target - existing)
    if swaps > min(len(validation_slots), len(promotion_slots)):
        raise ValueError('The critical allocation cannot fit both panels')
    for left, right in zip(validation_slots[:swaps], promotion_slots[:swaps]):
        validation[left], promotion[right] = promotion[right], validation[left]
    return validation, promotion


def cpo_candidate(incumbent, metadata, matrix, ordering, earlier, train, validation, seed, plan):
    paid = {}
    original = restart.search

    def capture(initial, train_rows, validation_rows, evaluate, propose, **settings):
        def observe(prompt, row):
            measured = evaluate(prompt, row)
            paid[prompt, row.id] = measured
            return measured

        return original(initial, train_rows, validation_rows, observe, propose, **settings)

    with patch.object(restart, 'search', capture):
        head, count, proposed = restart.run_cpo(incumbent, metadata, matrix, ordering, train, validation, seed, plan)
    seen = {prompt for _, prompt in proposed}
    unused = [prompt for prompt in ordering.get(incumbent, ()) if prompt in earlier and prompt not in seen]
    rows = [Row(case, 'task', metadata[case]['critical']) for case in validation]
    journal = set()

    def evaluate(prompt, row):
        key = prompt, row.id
        if row.id not in validation or key in paid or key in journal:
            raise ValueError('Archive screen requested duplicate evidence or a row outside validation')
        journal.add(key)
        return Observation(matrix[prompt][row.id][0], {})

    selected, continuation, attempts = screened.screen(
        head, unused, paid, rows, evaluate, metric_limit=plan['metricLimit'] - count,
        candidate_limit=min(8, plan['proposalSlots'] - len(proposed)), certified=True)
    if continuation != len(journal):
        raise ValueError('Screen exceeded its observed replay accounting')
    return selected, count + continuation, proposed + [(incumbent, item['prompt']) for item in attempts]


def compare(data, holdout, seed, plan, run_gepa):
    (root, metadata, matrix, original, _), graph, incumbent, _ = data
    available = sorted(metadata.keys() - set(holdout))
    Random(seed).shuffle(available)
    train, val_pool, promotion_pool = (available[start:start + 3] for start in (0, 3, 6))
    ordering, earlier = restart.proposal_graph(graph, root, incumbent, seed, 'mixed')
    arms, allocations, shared = {}, {}, {}
    for policy, minimum in POLICIES.items():
        validation, promotion = assign_panels(val_pool, promotion_pool, metadata, minimum)
        allocations[policy] = {'validationCritical': sum(metadata[case]['critical'] for case in validation),
                               'promotionCritical': sum(metadata[case]['critical'] for case in promotion),
                               'swaps': sum(case not in promotion_pool for case in promotion)}
        key = tuple(validation), tuple(promotion)
        if key not in shared:
            contestants = {'cpo': cpo_candidate(incumbent, metadata, matrix, ordering, earlier, train, validation, seed, plan)}
            for width, arm in enumerate(METHODS[1:], 1):
                result = run_gepa(incumbent, train, validation, metadata, matrix, ordering, seed, width=width, fields=True)
                proposals = [(step['parent'], step['recordedChild']) for step in result['proposerSteps']]
                contestants[arm] = result['selected'], result['searchCalls'], proposals
            records = {}
            for arm, (candidate, cost, proposals) in contestants.items():
                selected, status, qualification, receipt = restart.qualify(incumbent, candidate, metadata, matrix, promotion)
                if cost > plan['metricLimit'] or len(proposals) > plan['proposalSlots'] or qualification > 6:
                    raise ValueError('Replay exceeded its search or promotion cap')
                records[arm] = {'challenger': candidate, 'chosen': selected, 'promotion': status, 'qualification': receipt,
                                'archiveLookups': sum(parent == incumbent and child in earlier for parent, child in proposals),
                                'searchEvaluations': cost, 'proposalSlots': len(proposals),
                                'qualificationEvaluations': qualification, 'calls': cost + len(proposals) + qualification,
                                'outcomes': {case: matrix[selected][case][0] for case in holdout},
                                'originalHoldout': {case: score[0] for case, score in original.get(selected, {}).items()}}
            shared[key] = records
        arms.update({f'{arm}.{policy}': record for arm, record in shared[key].items()})
    return {'seed': seed, 'holdout': holdout, 'critical': [case for case in holdout if metadata[case]['critical']],
            'allocations': allocations, 'arms': arms}


def summarize(trials):
    with patch.object(restart, 'PRIMARY', PRIMARY):
        results = restart.summarize(trials)
    results['allocations'] = {}
    for policy in POLICIES:
        rows = [trial['allocations'][policy] for trial in trials]
        results['allocations'][policy] = {key: sum(info[key] for info in rows)
                                           for key in ('promotionCritical', 'validationCritical', 'swaps')}
        results['allocations'][policy]['promotionPanelsWithoutCritical'] = sum(not info['promotionCritical'] for info in rows)
    return results


def prepare():
    old, data, run_gepa = screened.prepare()
    seal = digest(old)
    path = Path(__file__)
    hashes = {**old['sourceSha256'], 'benchmarks/recorded_promotion_coverage.py': sha256(path.read_bytes()).hexdigest()}
    cohorts = {task: list(combinations(sorted(inputs[0][1]), 3)) for task, inputs in data.items()}
    plan = {**old, 'protocol': 'cpo-recorded-promotion-coverage-v1', 'baseScreenPlanSha256': seal,
            'primary': PRIMARY, 'policies': POLICIES, 'sourceSha256': hashes, 'seedStart': SEED_START, 'seedStride': 53,
            'holdoutDigests': {task: digest(rows) for task, rows in cohorts.items()}}
    del plan['seeds']
    return plan, data, run_gepa, cohorts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, run_gepa, cohorts = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {task: summarize([compare(inputs, holdout, plan['seedStart'] + index * plan['seedStride'], plan, run_gepa)
                               for index, holdout in enumerate(cohorts[task])]) for task, inputs in sorted(data.items())}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
