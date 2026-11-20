"""Replay the typed fixture with a proposer driven by paid training errors."""

from collections import Counter
from importlib.metadata import version
import json
from unittest.mock import patch

from benchmarks import feedback_budget, gepa_disjoint_cases, opening_screen_typed, typed_policy
from benchmarks.gepa_sequential_schedule import select_field_rewrites, traced_native_schedule
from cpo._contract import digest


def compare(task, cohorts, seed, cap):
    train_ids = {row['id'] for row in cohorts['train']}

    def run(paired):
        schedule, reads, proposals, nominees = [], [], [], []

        def select(initial, bank, groups, evaluate, reflect, *, cap, seed, width):
            if width != 1:
                return gepa_disjoint_cases.select(initial, bank, groups, evaluate, reflect, cap=cap, seed=seed,
                                                  width=width)

            def read(prompt, case):
                reads.append((prompt, case))
                return evaluate(prompt, case)

            def propose(parent, feedback):
                examples = sorted(feedback_budget.observation_records(feedback), key=lambda item: item['id'])
                if not examples or any(item['id'] not in train_ids for item in examples):
                    raise ValueError('Every later proposal must use paid training feedback')
                child = reflect(parent, examples)
                proposals.append((parent, examples, child))
                return child

            def baseline(start, opening, splits, observe, **options):
                return gepa_disjoint_cases.select(start, opening, splits, observe, propose, **options)

            if paired:
                nominee = select_field_rewrites(initial, bank, groups, read, propose, schedule, cap=cap, seed=seed)
            else:
                nominee = traced_native_schedule(baseline, initial, bank, groups, read, schedule,
                                                 cap=cap, seed=seed, width=width)
            nominees.append(nominee)
            return nominee

        with patch.object(opening_screen_typed, 'gepa_select', select):
            run = opening_screen_typed.trial(task, cohorts, seed, cap)
        return run['arms']['gepa-sequential'], schedule, nominees, proposals, reads

    native, schedule, nominees, proposals, paid = run(False)
    paired, new_schedule, new_nominees, new_proposals, new_paid = run(True)
    if (schedule, nominees, proposals) != (new_schedule, new_nominees, new_proposals):
        raise ValueError('The paired selector changed the native search or proposal trace')
    if any(native[key] != paired[key] for key in ('selectedSha256', 'qualificationLookups', 'holdout')):
        raise ValueError('The paired selector changed the admitted prompt or holdout')
    if (len(new_paid) != len(set(new_paid)) or not set(new_paid) <= set(paid)
            or len(new_paid) != paired['searchLookups']):
        raise ValueError('The paired selector exceeded the native paid read set')
    return {
        'seed': seed, 'task': task, 'passed': sum(native['holdout'].values()), 'nativeReads': len(paid),
        'pairedReads': len(new_paid), 'admissionReads': paired['qualificationLookups'],
        'feedbackProposals': len(proposals), 'changedPromptsFromFeedback': sum(p != c for p, _, c in proposals),
        'traceSha256': digest((native, paired, schedule, proposals)),
    }


def measure():
    cohorts = {seed: typed_policy.cohorts(seed) for seed in feedback_budget.SEEDS}
    results = {}
    for cap in feedback_budget.BUDGETS:
        records = [compare(task, cases, seed, cap) for seed, tasks in cohorts.items() for task, cases in tasks.items()]
        summary = Counter()
        for row in records:
            summary.update({key: value for key, value in row.items() if type(value) is int and key != 'seed'})
        results[cap] = {'paths': len(records), **summary, 'traceSha256': digest(records)}
    return {'schema': 'sequential-field-feedback-fixture-v1', 'newProviderRequests': 0, 'caps': results}


if __name__ == '__main__':
    if version('gepa') != '0.1.4':
        raise SystemExit('Use pinned GEPA 0.1.4')
    print(json.dumps(measure(), indent=2, sort_keys=True))
