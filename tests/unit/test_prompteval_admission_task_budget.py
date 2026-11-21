"""Check the minimum-cost score calculation against exhaustive allocation."""

from itertools import product

from benchmarks.prompteval_admission_task_budget import match_score


def test_dual_frontier_finds_the_cheapest_allocation_for_each_reachable_score():
    tasks = {'a': {'maxPasses': 12}, 'b': {'maxPasses': 12}}
    choices = {
        'a': [{'method': 'retain-start', 'cap': 0, 'paidLookups': 0, 'holdoutPasses': 2},
              {'method': 'sequential', 'cap': 4, 'paidLookups': 3, 'holdoutPasses': 7},
              {'method': 'batched', 'cap': 8, 'paidLookups': 5, 'holdoutPasses': 8}],
        'b': [{'method': 'retain-start', 'cap': 0, 'paidLookups': 0, 'holdoutPasses': 4},
              {'method': 'sequential', 'cap': 4, 'paidLookups': 4, 'holdoutPasses': 8},
              {'method': 'batched', 'cap': 8, 'paidLookups': 5, 'holdoutPasses': 11}],
    }
    known = [(sum(row['paidLookups'] for row in pair), sum(row['holdoutPasses'] for row in pair))
             for pair in product(*choices.values())]
    for score in range(25):
        eligible = [(cost, -passes) for cost, passes in known if passes >= score]
        result = match_score(tasks, choices, score)
        if eligible:
            cost, negative_passes = min(eligible)
            assert (result['paidLookups'], result['holdoutPasses']) == (cost, -negative_passes)
            chosen = [next(row for row in choices[point['subject']] if row['method'] == point['method'])
                      for point in result['allocation']]
            assert sum(row['paidLookups'] for row in chosen) == cost
            assert sum(row['holdoutPasses'] for row in chosen) == -negative_passes
        else:
            assert result is None
