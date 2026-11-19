from collections import Counter
from itertools import product
import unittest

from benchmarks.minimum_proof_budget import select_with_minimum_proof
from cpo import Observation, Row


class MinimumProofBudgetTests(unittest.TestCase):
    rows = (Row('0', 'task'), Row('1', 'task'), Row('2', 'task', True))

    def choose(self, scores, cap, fallback):
        lookups = []

        def evaluate(prompt, row):
            lookups.append((prompt, row.id))
            return Observation(scores[prompt][int(row.id)], {})

        result = select_with_minimum_proof('inc', ('a', 'b'), self.rows, evaluate,
                                          metric_limit=cap, fallback=fallback, audit=Counter())
        self.assertEqual(result.evaluations, len(lookups))
        self.assertEqual(len(lookups), len(set(lookups)))
        self.assertLessEqual(len(lookups), cap)
        return result

    def test_can_prove_a_gain_when_no_full_challenger_fits(self):
        scores = {'inc': (False, False, False), 'a': (True, False, False), 'b': (False, False, False)}
        self.assertEqual(self.choose(scores, 4, fallback=True).prompt, 'a')

    def test_all_binary_outcomes_preserve_strict_gain_and_critical_pass(self):
        for triple in product(product((False, True), repeat=3), repeat=3):
            scores = dict(zip(('inc', 'a', 'b'), triple, strict=True))
            for cap, fallback in product((3, 4, 5, 6, 9), (False, True)):
                result = self.choose(scores, cap, fallback)
                if result.prompt != 'inc':
                    self.assertGreater(sum(scores[result.prompt]), sum(scores['inc']))
                    self.assertTrue(not scores['inc'][2] or scores[result.prompt][2])
