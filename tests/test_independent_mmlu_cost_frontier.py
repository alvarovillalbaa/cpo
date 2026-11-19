import unittest

from benchmarks.independent_mmlu_cost_frontier import compare_cost, frontier


class IndependentMmluCostFrontierTests(unittest.TestCase):
    def test_cost_matching_uses_realized_cost_and_keeps_hindsight_distinct(self):
        seq, batch = frontier.gepa.METHODS
        fixed = {seq: {'44': {'holdoutPasses': 10, 'paidLookups': 11}},
                 batch: {'40': {'holdoutPasses': 9, 'paidLookups': 9},
                         '52': {'holdoutPasses': 12, 'paidLookups': 14}}}
        choices = {
            'left': [{'method': 'retain-start', 'cap': 0, 'holdoutPasses': 4, 'paidLookups': 0},
                     {'method': seq, 'cap': 44, 'holdoutPasses': 4, 'paidLookups': 6}],
            'right': [{'method': 'retain-start', 'cap': 0, 'holdoutPasses': 3, 'paidLookups': 0},
                      {'method': seq, 'cap': 44, 'holdoutPasses': 6, 'paidLookups': 5}],
        }
        result = compare_cost({'holdoutPasses': 10, 'paidLookups': 10}, fixed, choices)
        self.assertEqual(result['bestFixedGepaWithinCost']['method'], batch)
        self.assertEqual(result['cheapestFixedGepaMatchingPasses']['paidLookups'], 11)
        self.assertEqual(result['taskGepaWithRetainStartWithinCost']['holdoutPasses'], 10)
        self.assertEqual(result['taskGepaWithRetainStartWithinCost']['paidLookups'], 5)
