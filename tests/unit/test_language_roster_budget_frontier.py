from functools import partial
from itertools import product

from benchmarks.language_roster_budget_frontier import RETAIN, Point, efficient, episode_model, pool
from cpo.quoted_shared_validation_cycle import _screen
from cpo.two_sided_certificate_cycle import _run


def test_pooled_frontier_matches_brute_force_at_every_budget():
    menus = [
        [Point(1, 0, ('keep',)), Point(2, 2, ('wide',)), Point(3, 4, ('deep',))],
        [Point(2, 0, ('keep',)), Point(3, 1, ('wide',)), Point(5, 5, ('deep',))],
        [Point(1, 0, ('keep',)), Point(5, 3, ('wide',)), Point(3, 3, ('dominated',))],
    ]
    choices = [(sum(point.passes for point in rows), sum(point.cost for point in rows))
               for rows in product(*menus)]
    for budget in range(14):
        expected = max((score, -cost) for score, cost in choices if cost <= budget)
        selected = pool(menus, budget)
        assert (sum(point.passes for point in selected), -sum(point.cost for point in selected)) == expected
        assert all(point in menu for point, menu in zip(selected, menus, strict=True))


def test_cheapest_arrival_pruning_preserves_the_exhaustive_paid_frontier():
    cells = {
        'base': (False, False, False, False, False, False),
        'a': (True, True, False, False, True, False),
        'b': (True, True, True, True, False, False),
        'c': (False, False, True, True, True, True),
    }
    stages = [
        (0, ('a', 'b'), ((), (0,), (1,), (4, 5))),
        (1, ('c',), ((), (2,), (3,), (4, 5))),
    ]
    fixed = {RETAIN: None, 'quoted': partial(_run, screen=partial(_screen, halve=False))}
    singles = {'first': (0, 1), 'second': (1, 1)}
    plan = {'controls': [('test', 'uniform', 2, 4)]}
    replay, expand, clear = episode_model(plan, cells, stages, fixed, singles)
    actions = (*fixed, *singles)
    expanded = efficient(expand('base', actions))
    exhaustive = efficient(replay('base', sequence)[0] for sequence in product(actions, repeat=len(stages)))
    assert expanded == exhaustive
    assert max(point.passes for point in expanded) == 2
    clear()
