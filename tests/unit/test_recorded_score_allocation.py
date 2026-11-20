from fractions import Fraction
from itertools import product
import unittest

from benchmarks.recorded_score_allocation import allocate, predictive_chance
from cpo import Observation, Row


class ScoreAllocationTests(unittest.TestCase):
    def test_beta_binomial_probability_uses_paid_passes(self):
        self.assertEqual(predictive_chance(0, 0, 2, 1), Fraction(2, 3))
        self.assertEqual(predictive_chance(1, 0, 1, 2), Fraction(2, 3))
        self.assertEqual(predictive_chance(1, 1, 1, 2), Fraction(1, 2))
        self.assertEqual(predictive_chance(1, 0, 1, 3), 0)

    def test_funded_allocation_matches_full_ranking_and_preserves_critical_cases(self):
        rows = tuple(Row(str(i), 'task', critical=i == 0) for i in range(3))
        prompts = ('start', 'first', 'second')
        for bits in product((False, True), repeat=9):
            matrix = dict(zip(prompts, (bits[:3], bits[3:6], bits[6:]), strict=True))
            ledger = {}

            def observe(prompt, row):
                key = (prompt, row.id)
                self.assertNotIn(key, ledger)
                ledger[key] = Observation(matrix[prompt][int(row.id)], {})
                return ledger[key]

            eligible = [p for p in prompts if matrix[p][0] or not matrix['start'][0]]
            expected = max(eligible, key=lambda prompt: sum(matrix[prompt]))
            self.assertEqual(allocate('start', prompts[1:], rows, observe, ledger, limit=9), expected)
            self.assertLessEqual(len(ledger), 9)

    def test_small_budget_does_not_buy_unfunded_challenge(self):
        rows = tuple(Row(str(i), 'task') for i in range(3))
        journal = {}

        def observe(prompt, row):
            self.assertEqual(prompt, 'start')
            journal[prompt, row.id] = Observation(False, {})
            return journal[prompt, row.id]

        self.assertEqual(allocate('start', ['challenger'], rows, observe, journal, limit=5), 'start')
        self.assertEqual(len(journal), 3)
