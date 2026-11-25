from itertools import product

from benchmarks.validation_routed_certificate_floor import certificate


PANELS = tuple(product((False, True), repeat=6))
PRICE = (2, 11, 0, 7, 23, 1)


def winner_and_scores(panel):
    scores = tuple(sum(panel[index:index + 2]) for index in range(0, 6, 2))
    winner = max(range(3), key=scores.__getitem__)
    return winner, scores[0], scores[winner]


def test_weighted_certificate_floor_matches_all_paid_subsets_and_unread_completions():
    profiles = {panel: winner_and_scores(panel) for panel in PANELS}
    subsets = tuple(tuple(index for index in range(6) if mask & (1 << index)) for mask in range(64))
    costs = tuple(PRICE[index:index + 2] for index in range(0, 6, 2))
    for panel in PANELS:
        winner, _, _ = profiles[panel]
        grades = tuple(panel[index:index + 2] for index in range(0, 6, 2))
        for paid, complete in product(((), (0,), (0, 1)), (False, True)):
            observed_costs = []
            size = 3 if complete and winner else 1
            needed = profiles[panel][:size]
            for subset in subsets:
                if not set(paid).issubset(subset):
                    continue
                compatible = (other for other in PANELS if all(panel[index] == other[index] for index in subset))
                if all(profiles[other][:size] == needed for other in compatible):
                    observed_costs.append(sum(PRICE[index] for index in subset))
            assert certificate(grades, costs, winner, paid, complete_scores=complete) == min(observed_costs)
