from collections import Counter
from itertools import product
import unittest

from benchmarks.partial_pair_budget import METHODS, select_partial_pair
from cpo import Observation, Row


class PartialPairBudgetTests(unittest.TestCase):
    rows = (Row('0', 'task'), Row('1', 'task'), Row('2', 'task', True))

    def choose(self, scores, cap, method, rows=None):
        calls, audit = [], Counter()

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(scores[prompt][int(row.id)], {})

        result = select_partial_pair('inc', ('a', 'b'), rows or self.rows, evaluate,
                                     metric_limit=cap, method=method, audit=audit)
        self.assertEqual(result.evaluations, len(calls))
        self.assertLessEqual(len(calls), cap)
        self.assertEqual(len(calls), len(set(calls)))
        return result, audit

    def test_can_prove_gain_without_reading_the_full_incumbent(self):
        rows = tuple(Row(str(i), 'task') for i in range(3))
        scores = {'inc': (False, False, True), 'a': (True, True, True), 'b': (False, False, False)}
        result, audit = self.choose(scores, 4, 'row-order', rows=rows)
        self.assertEqual(result.prompt, 'a')
        self.assertEqual(audit['certificatesWithoutFullIncumbent'], 1)

    def test_binary_proofs_respect_caps_and_critical_passes(self):
        for vector in product(product((False, True), repeat=3), repeat=3):
            scores = dict(zip(('inc', 'a', 'b'), vector, strict=True))
            for cap, method in product((3, 4, 5, 6, 9), METHODS):
                result, _ = self.choose(scores, cap, method)
                if result.prompt != 'inc':
                    self.assertGreater(sum(scores[result.prompt]), sum(scores['inc']))
                    self.assertTrue(not scores['inc'][2] or scores[result.prompt][2])
