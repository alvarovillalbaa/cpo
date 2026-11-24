"""T2 mock trajectories and archive budget points."""

import pytest

from benchmarks.promotion_aware_archive_routing import budget_bounds, choose_actions, rollout


def point(passes, cost):
    return {'holdoutPasses': passes, 'paidLookups': cost}


def test_switches_after_the_first_verified_promotion_and_keeps_the_incumbent():
    measured = []

    def transition(cycle, prompt, action):
        measured.append((cycle, prompt, action))
        return ('winner' if cycle == 1 else prompt), 3, str(cycle)

    final, cost, path = rollout('start', 3, ('cold', 'warm'), transition)
    assert measured == [(0, 'start', 'cold'), (1, 'start', 'cold'), (2, 'winner', 'warm')]
    assert (final, cost) == ('winner', 9)
    assert path == [('start', 'start', '0'), ('start', 'winner', '1'), ('winner', 'winner', '2')]


def test_fitting_respects_each_cohort_cap_and_uses_the_same_action_control():
    points = {('a', 'a'): {'one': point(5, 7), 'two': point(4, 3)},
              ('b', 'b'): {'one': point(5, 6), 'two': point(4, 3)},
              ('a', 'b'): {'one': point(6, 7), 'two': point(4, 3)},
              ('b', 'a'): {'one': point(9, 8), 'two': point(9, 1)}}
    budgets = {'one': 7, 'two': 4}
    assert choose_actions(points, budgets, False) == ('a', 'b')
    assert choose_actions(points, budgets, True) == ('b', 'b')


def test_native_anchor_ranges_use_attaining_cost_for_the_lower_and_budget_for_the_upper():
    menu = {'smaller': point(20, 9), 'larger': point(24, 17)}
    budgets = {'smaller': point(0, 12), 'larger': point(0, 23)}
    middle = budget_bounds(menu, budgets, 15, 18)
    assert (middle['lowerPasses'], middle['upperPasses'], middle['attainer']) == (20, 24, menu['smaller'])
    assert budget_bounds(menu, budgets, 17, 18)['lowerPasses'] == 24
    assert budget_bounds(menu, budgets, 30, 18)['upperPasses'] is None


def test_empty_feasible_fixed_set_is_reported_even_when_a_switch_fits():
    points = {('a', 'a'): {'one': point(9, 8)}, ('a', 'b'): {'one': point(8, 7)}}
    assert choose_actions(points, {'one': 7}, False) == ('a', 'b')
    with pytest.raises(ValueError, match='fits the frozen per-cohort caps'):
        choose_actions(points, {'one': 7}, True)
