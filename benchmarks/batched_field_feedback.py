"""Compare multi-round paired field validation with native same-parent GEPA."""

import argparse
from collections import Counter
from importlib.metadata import version
import json
from unittest.mock import patch

from benchmarks import feedback_budget, gepa_disjoint_cases, grounded, opening_screen_typed, typed_policy
from benchmarks.gepa_sequential_schedule import sequential_schedule, traced_native_schedule
from benchmarks.sequential_field_feedback import REPLICATION_SEEDS
from cpo import Row
from cpo._contract import digest
from cpo.batched_field_rewrite import select_batched_field_rewrites


WIDTH = 2
CAPS = (32, 56, 76)


def compare_search(initial, bank, groups, evaluate, reflect, *, cap, seed, paired, frontier_bounds=False):
    trace, paid, proposals = [], [], []
    train_ids = {row['id'] for row in groups['train']}

    def read(prompt, case):
        paid.append((prompt, case))
        return evaluate(prompt, case)

    def later(parent, feedback):
        examples = sorted(feedback_budget.observation_records(feedback), key=lambda item: item['id'])
        if not examples or any(row['id'] not in train_ids for row in examples):
            raise ValueError('A later proposal must receive only paid training rows')
        child = reflect(parent, examples)
        proposals.append((parent, examples, child))
        return child

    def native(start, opening, splits, observe, **options):
        return gepa_disjoint_cases.select(start, opening, splits, observe, later, **options)

    if paired:
        training, validation = (
            tuple(Row(row['id'], 'fixture', fields=len(row['expected'])) for row in groups[split])
            for split in ('train', 'validation')
        )
        schedule = sequential_schedule(validation, seed, grounded.MINIBATCH, trace,
                                       training=training, parent_bounds=True, width=WIDTH,
                                       frontier_bounds=frontier_bounds)

        def propose(index, parent, samples):
            if index < len(bank):
                return bank[index]
            return later(parent, [observation.feedback for _, observation in samples])

        nominee = select_batched_field_rewrites(
            initial, training, validation, lambda prompt, row: read(prompt, row.id), schedule, propose,
            rounds=grounded.REFLECTION_LIMIT // WIDTH, width=WIDTH, minibatch_size=grounded.MINIBATCH,
            metric_limit=cap,
        )
    else:
        nominee = traced_native_schedule(native, initial, bank, groups, read, trace, cap=cap, seed=seed, width=WIDTH)
    return nominee, trace, paid, proposals


def run_arm(task, groups, seed, cap, *, paired, frontier_bounds=False):
    record = None

    def select(initial, bank, splits, evaluate, reflect, *, cap, seed, width):
        nonlocal record
        if width != WIDTH:
            return gepa_disjoint_cases.select(initial, bank, splits, evaluate, reflect, cap=cap, seed=seed,
                                              width=width)
        record = compare_search(initial, bank, splits, evaluate, reflect, cap=cap, seed=seed, paired=paired,
                                frontier_bounds=frontier_bounds)
        return record[0]

    with patch.object(opening_screen_typed, 'gepa_select', select):
        row = opening_screen_typed.trial(task, groups, seed, cap)['arms']['gepa-batched']
    if record is None or len(record[2]) != len(set(record[2])) or len(record[2]) != row['searchLookups']:
        raise ValueError('The batched search lookup accounting differs from its paid reads')
    return row, record


def compare(task, groups, seed, cap, *, frontier_bounds=False):
    native, (old, old_trace, old_paid, old_proposals) = run_arm(task, groups, seed, cap, paired=False)
    cpo, (selected, trace, paid, proposals) = run_arm(task, groups, seed, cap, paired=True,
                                                     frontier_bounds=frontier_bounds)
    if (old, old_trace, old_proposals) != (selected, trace, proposals):
        raise ValueError(f'The batched decision or later proposal changed at {task=} {seed=} {cap=}')
    if any(native[key] != cpo[key] for key in ('selectedSha256', 'qualificationLookups', 'holdout', 'proposalCalls')):
        raise ValueError('Batched pairing changed independent admission or held-out outcomes')
    if not set(paid) <= set(old_paid):
        raise ValueError('Batched pairing read a reply outside the native paid set')
    return {'nativeReads': len(old_paid), 'pairedReads': len(paid), 'admissionReads': cpo['qualificationLookups'],
            'heldOutPasses': sum(cpo['holdout'].values()), 'laterProposals': len(proposals),
            'changedParents': sum(parent != pool[0] for pool, parent, _ in trace[::WIDTH]),
            'pathSha256': digest((task, seed, native, cpo, trace, proposals))}


def measure(*, frontier_bounds=False):
    reports = {}
    for cap in CAPS:
        paths = [compare(task, groups, seed, cap, frontier_bounds=frontier_bounds)
                 for seed in (*feedback_budget.SEEDS, *REPLICATION_SEEDS)
                 for task, groups in typed_policy.cohorts(seed).items()]
        totals = Counter()
        for path in paths:
            totals.update({key: value for key, value in path.items() if type(value) is int})
        reports[cap] = {**totals, 'paths': len(paths), 'traceSha256': digest(paths)}
    schema = 'batched-field-frontier-bounds-v1' if frontier_bounds else 'batched-field-feedback-fixture-v1'
    return {'schema': schema, 'gepaVersion': '0.1.4',
            'newProviderRequests': 0, 'caps': reports}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontier-bounds', action='store_true', help='Prove parent draws for larger pools')
    args = parser.parse_args()
    if version('gepa') != '0.1.4':
        raise SystemExit('Use pinned GEPA 0.1.4')
    print(json.dumps(measure(frontier_bounds=args.frontier_bounds), indent=2, sort_keys=True))
