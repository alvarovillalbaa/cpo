"""T2 mock discovery costs and held-out scores."""

from itertools import product

import pytest

from benchmarks.cohort_budgeted_archive_routing import fit_table


def point(passes, lookups):
    return {'holdoutPasses': passes, 'paidLookups': lookups}


@pytest.mark.parametrize('percentage,nonloss', [(95, False), (100, True)])
def test_fit_matches_exhaustive_optimum_with_local_caps_and_sparse_states(percentage, nonloss):
    menus = {
        'a': {'first': {'base': point(10, 10), 'broad': point(15, 14), 'retain': point(4, 1)},
              'second': {'base': point(8, 12), 'broad': point(9, 11), 'retain': point(3, 1)}},
        'b': {'first': {'base': point(8, 11), 'broad': point(7, 7), 'retain': point(3, 1)},
              'second': {'base': point(4, 7), 'broad': point(6, 5), 'retain': point(3, 1)},
              'third': {'base': point(2, 5), 'broad': point(2, 5), 'retain': point(2, 4)}},
    }
    actions = ('broad', 'retain', 'base')
    states = ('first', 'second', 'third')
    closed = {'a': point(7, 3), 'b': point(5, 4)}
    base = {'a': point(25, 25), 'b': point(19, 27)}
    feasible = []
    for choices in product(actions, repeat=len(states)):
        points = {}
        for cohort, menu in menus.items():
            known = [closed[cohort], *(menu[state][choice] for state, choice in zip(states, choices) if state in menu)]
            score = sum(row['holdoutPasses'] for row in known)
            cost = sum(row['paidLookups'] for row in known)
            budget = base[cohort]['paidLookups'] * percentage // 100
            if cost > budget or (nonloss and score < base[cohort]['holdoutPasses']):
                break
            points[cohort] = {**point(score, cost), 'budget': budget}
        if points.keys() == menus.keys():
            feasible.append(((-sum(p['holdoutPasses'] for p in points.values()),
                              sum(p['paidLookups'] for p in points.values()), choices), points))
    rank, expected = min(feasible)
    actual = fit_table(menus, closed, base, percentage, nonloss, actions=actions)
    assert actual == {'actions': dict(zip(states, rank[2])), 'byCohort': expected}


def test_cannot_offset_a_cohort_budget_overrun_with_another_cohorts_savings():
    menus = {'a': {'one': {'base': point(3, 4), 'mixed': point(7, 6)}},
             'b': {'one': {'base': point(3, 4), 'mixed': point(5, 2)}}}
    closed = dict.fromkeys(menus, point(0, 0))
    base = dict.fromkeys(menus, point(3, 4))
    assert fit_table(menus, closed, base, 100, False, actions=('base', 'mixed'))['actions'] == {'one': 'base'}
