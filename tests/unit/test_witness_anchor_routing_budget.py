from itertools import product

from benchmarks import witness_anchor_routing_budget as replay


def subject(wide_cost):
    cases = {rule: [0, 0] for rule in replay.parent.PROBE_MENU}
    costs = dict.fromkeys(cases, 8)
    cases[replay.BOUNDS] = [1, 1]
    costs[replay.BOUNDS] = wide_cost
    costs[replay.retry.BASE] = 10
    return {'cases': cases, 'costs': costs, 'wideEpisodes': dict.fromkeys(cases, 0), 'decisionsPerCase': 1}


def test_drop_one_rejects_a_fit_that_depends_on_one_training_subject():
    groups = [subject(cost) for cost in (8, 11, 10)]

    assert replay.parent.fit(groups, replay.parent.PROBE_MENU) == replay.BOUNDS
    assert replay.fit(groups, replay.DROP_ONE) == replay.FULL


def test_individual_budget_fit_rejects_an_overage_the_drop_one_rule_tolerates():
    groups = [subject(cost) for cost in (8, 8, 11)]

    assert replay.fit(groups, replay.DROP_ONE) == replay.BOUNDS
    assert replay.fit(groups, replay.EACH) == replay.FULL


def test_exact_mixture_matches_enumeration_at_every_feasible_budget():
    episodes = (('a', (8, 7), (3, 4)), ('a', (4, 1), (5, 5)),
                ('b', (3, 3), (3, 6)), ('b', (2, 5), (3, 4)))
    for weights in ({'a': 1, 'b': 1}, {'a': 1, 'b': 3}):
        portfolios = []
        for choices in product((1, 2), repeat=len(episodes)):
            cost = sum(episode[choice][0] for episode, choice in zip(episodes, choices, strict=True))
            score = sum(episode[choice][1] * weights[episode[0]]
                        for episode, choice in zip(episodes, choices, strict=True))
            portfolios.append((score, cost))
        for budget in range(min(cost for _, cost in portfolios), max(cost for _, cost in portfolios) + 1):
            score, cost = max((row for row in portfolios if row[1] <= budget), key=lambda row: (row[0], -row[1]))
            assert replay.best_mixture(episodes, budget, weights) == {'score': score, 'paidLookups': cost}
