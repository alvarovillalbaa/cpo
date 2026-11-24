from itertools import product

import pytest

from benchmarks.promptolution_settled_episode_headroom import cost_frontier, evaluate, witness
from benchmarks.language_roster_budget_frontier import Point


def point(passes, cost, method):
    return Point(passes, cost, (method,))


def test_budgeted_frontier_and_attainers_match_exhaustive_choices():
    menus = (
        (point(1, 0, 'baseline'), point(5, 4, 'narrow'), point(7, 9, 'wide')),
        (point(3, 0, 'baseline'), point(6, 2, 'narrow'), point(7, 6, 'wide')),
        (point(2, 0, 'baseline'), point(4, 1, 'narrow'), point(4, 7, 'wide')),
    )
    exhaustive = [(sum(choice.passes for choice in options), sum(choice.cost for choice in options))
                  for options in product(*menus)]
    efficient = cost_frontier(menus)
    for budget in range(24):
        score, negative_cost = max((score, -cost) for score, cost in exhaustive if cost <= budget)
        actual = witness(menus, budget)
        assert (actual['holdoutPasses'], actual['paidLookups']) == (score, -negative_cost)
        assert efficient[score] == -negative_cost
        selected = [next(choice for choice in menu if choice.actions == (method,))
                    for menu, method in zip(menus, actual['settings'], strict=True)]
        assert sum(choice.passes for choice in selected) == score
        assert sum(choice.cost for choice in selected) == -negative_cost


@pytest.mark.parametrize('target', (6, 9, 11))
def test_inverse_cost_matches_and_reports_unreachable_scores(target):
    episodes = (
        {'baseline': point(2, 0, 'baseline'), 'control': point(5, 3, 'control'),
         'candidate': point(target - 3, 2, 'candidate')},
        {'baseline': point(1, 0, 'baseline'), 'control': point(4, 4, 'control'),
         'candidate': point(3, 2, 'candidate')},
    )
    result = evaluate(episodes, 'candidate', ('baseline', 'control'), {'controlPasses': 3})
    assert result['hindsightAtBudget']['holdoutPasses'] == 6
    assert result['unconstrainedHindsight'] == {'holdoutPasses': 9, 'paidLookups': 7}
    assert result['candidatePassesAboveHindsight'] == target - 6
    match = result['minimumCostToMatchCandidate']
    if target == 11:
        assert match is None
    else:
        assert match['holdoutPasses'] >= target
        assert match['paidLookups'] == (3 if target == 6 else 7)
