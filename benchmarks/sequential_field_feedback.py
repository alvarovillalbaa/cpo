"""Replay the typed fixture with a proposer driven by paid training errors."""

import argparse
from collections import Counter
from importlib.metadata import version
import json
from unittest.mock import patch

from benchmarks import feedback_budget, gepa_disjoint_cases, grounded, opening_screen_typed, typed_policy
from benchmarks.gepa_sequential_schedule import native_with_price_guard, select_field_rewrites, traced_native_schedule
from cpo._contract import digest
from cpo.sequential_field_rewrite import SequentialSearchBudget


REPLICATION_SEEDS = (47317, 47347, 47377, 47401, 47423, 47437)


def run_arm(task, cohorts, seed, cap, mode, *, reflection_price=None, parent_bounds=False):
    train_ids = {row['id'] for row in cohorts['train']}
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
            if reflection_price is not None:
                return native_with_price_guard(gepa_disjoint_cases.select, can_fund_round,
                                               start, opening, splits, observe, propose, **options)
            return gepa_disjoint_cases.select(start, opening, splits, observe, propose, **options)

        def quote(index, _parent=None):
            return 0 if index < len(bank) else reflection_price

        def can_fund_round(index):
            reserve = 2 * grounded.MINIBATCH + len(groups['validation'])
            return len(reads) + len(proposals) * reflection_price + reserve + quote(index) <= cap

        if mode == 'native':
            nominee = traced_native_schedule(baseline, initial, bank, groups, read, schedule,
                                             cap=cap, seed=seed, width=width)
        else:
            budget = None if reflection_price is None else SequentialSearchBudget(
                cap, 1, quote, lambda index, *_: quote(index),
            )
            nominee = select_field_rewrites(initial, bank, groups, read, propose, schedule, cap=cap, seed=seed,
                                             reinvest_savings=mode == 'reinvest', price_budget=budget,
                                             observed_charge=None if budget is None else lambda *_: 1,
                                             parent_bounds=parent_bounds)
        nominees.append(nominee)
        return nominee

    with patch.object(opening_screen_typed, 'gepa_select', select):
        run = opening_screen_typed.trial(task, cohorts, seed, cap)
    return run['arms']['gepa-sequential'], schedule, nominees, proposals, reads


def compare(task, cohorts, seed, cap, *, parent_bounds=False):
    native, schedule, nominees, proposals, paid = run_arm(task, cohorts, seed, cap, 'native')
    paired, new_schedule, new_nominees, new_proposals, new_paid = run_arm(
        task, cohorts, seed, cap, 'paired', parent_bounds=parent_bounds,
    )
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


def measure(*, parent_bounds=False):
    cohorts = {seed: typed_policy.cohorts(seed) for seed in feedback_budget.SEEDS}
    results = {}
    for cap in feedback_budget.BUDGETS:
        records = [compare(task, cases, seed, cap, parent_bounds=parent_bounds)
                   for seed, tasks in cohorts.items() for task, cases in tasks.items()]
        summary = Counter()
        for row in records:
            summary.update({key: value for key, value in row.items() if type(value) is int and key != 'seed'})
        results[cap] = {'paths': len(records), **summary, 'traceSha256': digest(records)}
    schema = 'sequential-field-parent-bounds-v1' if parent_bounds else 'sequential-field-feedback-fixture-v1'
    return {'schema': schema, 'newProviderRequests': 0, 'caps': results}


def compare_reinvestment(seeds):
    cohorts = {seed: typed_policy.cohorts(seed) for seed in seeds}
    modes = ('native', 'paired', 'reinvest')
    results = {}
    for cap in (40, 48, 56):
        paths, totals = [], {mode: Counter() for mode in modes}
        outcomes = Counter(pathsWithMorePasses=0, pathsWithFewerPasses=0, criticalLosses=0,
                           pathsWithMoreProposals=0, pathsWithMoreCalls=0)
        for seed, tasks in cohorts.items():
            for task, cases in tasks.items():
                traces = [run_arm(task, cases, seed, cap, mode) for mode in modes]
                for mode, (row, _, _, _, paid) in zip(modes, traces, strict=True):
                    if len(paid) > cap or len(paid) != len(set(paid)) or len(paid) != row['searchLookups']:
                        raise ValueError('The fixture run exceeded its paid search cap')
                    totals[mode].update(holdoutPasses=sum(row['holdout'].values()), searchReads=len(paid),
                                        admissionReads=row['qualificationLookups'], proposals=row['proposalCalls'])
                native, _, reinvest = (trace[0] for trace in traces)
                old, new = (sum(row['holdout'].values()) for row in (native, reinvest))
                native_calls, reinvest_calls = (
                    sum(row[key] for key in ('searchLookups', 'qualificationLookups', 'proposalCalls'))
                    for row in (native, reinvest))
                outcomes.update(pathsWithMorePasses=new > old, pathsWithFewerPasses=new < old,
                                criticalLosses=sum(row['critical'] and native['holdout'][row['id']]
                                                   and not reinvest['holdout'][row['id']] for row in cases['holdout']),
                                pathsWithMoreProposals=reinvest['proposalCalls'] > native['proposalCalls'],
                                pathsWithMoreCalls=reinvest_calls > native_calls)
                paths.append((task, seed, traces))
        for summary in totals.values():
            summary['countedCalls'] = sum(summary[key] for key in ('searchReads', 'admissionReads', 'proposals'))
        results[cap] = {'paths': len(paths), 'totals': totals, 'outcomes': outcomes, 'traceSha256': digest(paths)}
    return {'seeds': seeds, 'caps': results}


def measure_reinvestment():
    return {
        'schema': 'sequential-field-paid-budget-v1',
        'newProviderRequests': 0,
        'cohorts': {
            'published': compare_reinvestment(feedback_budget.SEEDS),
            'replication': compare_reinvestment(REPLICATION_SEEDS),
        },
    }


def measure_quoted_budget():
    cap = 48
    results = {}
    for reflection_price in (1, 4, 8):
        totals = {mode: Counter() for mode in ('native', 'reinvest')}
        changes = Counter(paths=0, criticalLosses=0, pathsWithMorePasses=0, pathsWithFewerPasses=0, pathsWithMoreCost=0)
        traces = []
        for seed in (*feedback_budget.SEEDS, *REPLICATION_SEEDS):
            for task, cases in typed_policy.cohorts(seed).items():
                path, costs, outcomes = [], [], []
                for mode, total in totals.items():
                    record = run_arm(task, cases, seed, cap, mode, reflection_price=reflection_price)
                    row, _, _, proposals, paid = record
                    search_charge = len(paid) + len(proposals) * reflection_price
                    if search_charge > cap or len(paid) != len(set(paid)) or len(paid) != row['searchLookups']:
                        raise ValueError('The charged fixture exceeded its common search quote')
                    cost = search_charge + 1 + row['qualificationLookups']
                    scores = row['holdout']
                    total.update(searchCharge=search_charge, totalCharge=cost, holdoutPasses=sum(scores.values()),
                                 searchReads=len(paid), laterProposals=len(proposals))
                    path.append(record)
                    costs.append(cost)
                    outcomes.append(scores)
                before, after = outcomes
                changes.update(paths=1, pathsWithMorePasses=sum(after.values()) > sum(before.values()),
                               pathsWithFewerPasses=sum(after.values()) < sum(before.values()),
                               pathsWithMoreCost=costs[1] > costs[0],
                               criticalLosses=sum(row['critical'] and before[row['id']] and not after[row['id']]
                                                  for row in cases['holdout']))
                traces.append((seed, task, path))
        results[reflection_price] = {**changes, 'totals': totals, 'traceSha256': digest(traces)}
    return {'schema': 'sequential-field-quote-fixture-v1', 'newProviderRequests': 0, 'searchQuote': cap, 'points': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--paid-budget', action='store_true', help='Let CPO spend saved reads on more rounds')
    modes.add_argument('--quoted-budget', action='store_true', help='Charge proposals against the same search quote')
    modes.add_argument('--parent-bounds', action='store_true', help='Prove the native draw from partial profiles')
    args = parser.parse_args()
    if version('gepa') != '0.1.4':
        raise SystemExit('Use pinned GEPA 0.1.4')
    if args.quoted_budget:
        report = measure_quoted_budget()
    else:
        report = measure_reinvestment() if args.paid_budget else measure(parent_bounds=args.parent_bounds)
    print(json.dumps(report, indent=2, sort_keys=True))
