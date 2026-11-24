from collections import Counter, defaultdict
from itertools import product

import pytest

from benchmarks.settled_episode_cycle_override import (
    BUDGET_ONLY, GUARDED, constant_paths, fit_tables, override_menus, rollout_graph,
)
from benchmarks.settled_episode_refit import RETAIN
from cpo.bounded_uniform_validation import run_bounded_uniform_cycle
from cpo.settled_episode_schedule import choose_schedule


@pytest.mark.parametrize('min_subjects', (1, 2))
def test_cycle_override_fits_against_settled_callback_counts(min_subjects):
    anchors = {'bounded': constant_paths(('bounded',) * 3),
               'frozen': constant_paths(('bounded', 'uniform', 'halving'))}
    options = ('bounded', 'halving', 'uniform')
    menus = tuple(override_menus(anchors, options))
    grades = ((False, False), (False, True), (True, False), (True, True))
    support = [1, 2, 1]
    cohorts = ('A', 'B')
    paths = {(state, path) for _, _, choices in menus for state, window in enumerate(choices) for path in window}

    def point(cohort, state, path):
        gaining_action = 'uniform' if cohort == 'A' else 'halving'
        return {'holdoutPasses': 5 + (path[state] == gaining_action) - (path[1] not in ('bounded', gaining_action)),
                'paidLookups': sum(3 if action == 'bounded' else 2 for action in path)}

    scores = defaultdict(Counter)
    counts = {cohort: Counter() for cohort in cohorts}
    baseline = {cohort: dict(holdoutPasses=20, paidLookups=36) for cohort in cohorts}
    for cohort in cohorts:
        for pair in grades:
            counts[cohort][pair[0]] += 1
            for state, path in paths:
                if state == sum(pair):
                    scores[cohort, state, path].update(point(cohort, state, path))
    actual = fit_tables(menus, anchors, baseline, counts, scores, support, min_subjects)
    tables = set()
    for name, index, choices in menus:
        for table in product(*choices):
            assert all(all(path[cycle] == anchor[cycle] for cycle in range(3) if cycle != index)
                       for path, anchor in zip(table, anchors[name], strict=True))
            if all(support[state] >= min_subjects or path == anchors[name][state]
                   for state, path in enumerate(table)):
                tables.add(table)

    ranked = {BUDGET_ONLY: [], GUARDED: []}
    for table in tables:
        points = {cohort: Counter() for cohort in cohorts}
        for cohort in cohorts:
            for pair in grades:
                paid = []

                def read(prompt, row):
                    paid.append(row)
                    return pair[row]

                path = choose_schedule('incumbent', range(2), read, actions=table)
                points[cohort].update(point(cohort, sum(pair), path), paidLookups=len(paid))
        if any(points[cohort]['paidLookups'] > baseline[cohort]['paidLookups'] for cohort in cohorts):
            continue
        item = (-sum(value['holdoutPasses'] for value in points.values()),
                sum(value['paidLookups'] for value in points.values()), table, points)
        ranked[BUDGET_ONLY].append(item)
        if all(points[cohort]['holdoutPasses'] >= baseline[cohort]['holdoutPasses'] for cohort in cohorts):
            ranked[GUARDED].append(item)

    assert actual['uniqueTables'] == len(tables)
    for mode, items in ranked.items():
        _, _, table, points = min(items)
        assert actual['feasibleTables'][mode] == len(items)
        assert actual['policies'][mode]['paths'] == table
        assert actual['policies'][mode]['points'] == points


def test_graph_counts_each_qualified_move_against_its_actual_incumbent():
    cells = {'start': (0, 0, 0, 0, 0), 'first': (1, 1, 1, 0, 0), 'second': (0, 0, 0, 1, 1)}
    stages = ((1, ('first',), ((), (0,), (1,), (2,))),
              (2, ('second',), ((), (3,), (4,), (2,))))
    plan = {'controls': (('uniform', 'uniform', 1, 2),)}
    rollout, clear = rollout_graph(plan, cells, stages, {'uniform': run_bounded_uniform_cycle})
    assert rollout('start', ('uniform', RETAIN)) == ([1], 4)
    assert rollout('start', ('uniform', 'uniform')) == ([0], 8)
    clear()
