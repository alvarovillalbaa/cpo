from itertools import product
import unittest

from benchmarks.paid_budget_frontier import best_fixed_gepa, best_subject_allocation, gepa


class PaidBudgetFrontierTests(unittest.TestCase):
    def test_cap_selection_uses_measured_prices_and_handles_infeasibility(self):
        seq, batch = gepa.METHODS
        totals = {
            seq: {'52': {'holdoutPasses': 9, 'paidLookups': 5}, '36': {'holdoutPasses': 7, 'paidLookups': 4}},
            batch: {'44': {'holdoutPasses': 8, 'paidLookups': 3}, '48': {'holdoutPasses': 8, 'paidLookups': 4}},
        }
        self.assertEqual(best_fixed_gepa(totals, 4), {
            'method': batch, 'cap': 44, 'holdoutPasses': 8, 'paidLookups': 3,
        })
        self.assertIsNone(best_fixed_gepa(totals, 2))

    def test_subject_allocation_matches_exhaustive_enumeration_at_each_budget(self):
        def points(cost_and_score):
            return [{'method': gepa.METHODS[i % 2], 'cap': 28 + i * 4, 'paidLookups': c, 'holdoutPasses': p}
                    for i, (c, p) in enumerate(cost_and_score)]

        choices = {'a': points([(1, 0), (3, 5), (4, 4)]),
                   'b': points([(2, 2), (4, 6), (5, 6)]),
                   'c': points([(0, 0), (1, 1), (5, 8)])}
        combinations = list(product(*choices.values()))
        for budget in range(17):
            costs_and_scores = [(sum(row['paidLookups'] for row in combo),
                                 sum(row['holdoutPasses'] for row in combo)) for combo in combinations]
            expected = max(((score, -cost) for cost, score in costs_and_scores if cost <= budget), default=None)
            actual = best_subject_allocation(choices, budget)
            if expected is None:
                self.assertIsNone(actual)
            else:
                self.assertEqual((actual['holdoutPasses'], -actual['paidLookups']), expected)
                self.assertEqual({row['subject'] for row in actual['allocation']}, set(choices))
