from itertools import combinations, product

from benchmarks import recorded_math_roster_ceiling as study


def test_certificate_floor_matches_exhaustive_sufficient_subsets():
    prompts, cases = ('old', 'new'), (0, 1)
    keys = tuple(product(prompts, cases))
    prices = dict(zip(keys, (8, 4, 6, 2), strict=True))
    for grades in product((False, True), repeat=4):
        board = dict(zip(keys, grades, strict=True))
        cells = {prompt: [(board[prompt, case], prices[prompt, case], False) for case in cases]
                 for prompt in prompts}
        for prefix_length in range(3):
            prefix = {case: board['old', case] for case in cases[:prefix_length]}
            prefix_keys = {('old', case) for case in prefix}
            unread = [key for key in keys if key not in prefix_keys]
            priced = []
            for width in range(len(unread) + 1):
                for chosen in combinations(unread, width):
                    known = {*prefix_keys, *chosen}
                    # Unread incumbent rows may all pass and unread challenger rows may all fail.
                    old = sum(board[key] if key in known else True for key in keys[:2])
                    new = sum(board[key] if key in known else False for key in keys[2:])
                    if new > old:
                        priced.append((width, sum(prices[key] for key in chosen)))
            expected = (study.Cost(min(count for count, _ in priced), min(amount for _, amount in priced))
                        if priced else None)
            assert study.certificate_floor(cells, *prompts, cases, prefix) == expected


def test_pooled_frontier_matches_every_combination_at_each_budget():
    menus = ([(0, 1), (4, 6), (6, 14), (3, 8)], [(0, 2), (3, 5), (8, 12)], [(0, 0), (7, 12)])
    all_choices = [(sum(gain for gain, _ in choice), sum(cost for _, cost in choice)) for choice in product(*menus)]
    frontier = {0: 0}
    for menu in menus:
        frontier = study.extend(frontier, menu)
    for budget in range(3, 40):
        result = study.summarize(frontier, 10, budget, 21)
        best = max(gain for gain, cost in all_choices if cost <= budget)
        assert result['ceilingPassesWithinBudget'] == best + 10
        assert result['costAtBudgetedCeiling'] == min(cost for gain, cost in all_choices if gain == best)
        assert result['minimumCostToBeatMatchedGEPA'] == min(cost for gain, cost in all_choices if gain > 11)


def test_nested_menus_charge_only_the_exact_gate_evidence():
    cells = {prompt: [(passed, 1, False) for passed in grades] for prompt, grades in {
        'start': (0, 0, 0, 0, 0, 0, 0, 0),
        'alpha': (0, 0, 1, 1, 1, 1, 1, 1),
        'beta': (1, 0, 1, 1, 1, 0, 1, 0),
        'gamma': (1, 0, 0, 0, 1, 1, 0, 0),
    }.items()}
    cohorts = ([0, 1], [2, 3], [4, 5], [6, 7])
    old, gain, menu = study.offers(cells, 'start', ('alpha', 'beta', 'gamma'), cohorts, 180)
    assert old == 0 and gain == 2
    assert set(menu[study.QUALIFIED]) == {'start', 'alpha', 'beta', 'gamma'}
    assert set(menu[study.VALIDATED]) == {'start', 'alpha', 'beta'}
    assert menu[study.TRAINED] == {'start': (0, study.Cost(1, 1)), 'beta': (1, study.Cost(8, 8))}
