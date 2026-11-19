from collections import Counter
from itertools import product
import unittest

from benchmarks.budgeted_second_probe import select_with_second_probe
from cpo import Observation, Row


class BudgetedSecondProbeTests(unittest.TestCase):
    rows = (Row('0', 'task'), Row('1', 'task'), Row('2', 'task', True))

    def choose(self, scores, limit, recheck):
        observed = []

        def evaluate(prompt, row):
            observed.append((prompt, row.id))
            return Observation(scores[prompt][int(row.id)], {})

        result = select_with_second_probe('inc', ('a', 'b'), self.rows, evaluate,
                                          metric_limit=limit, recheck=recheck, audit=Counter())
        self.assertEqual(result.evaluations, len(observed))
        self.assertEqual(len(observed), len(set(observed)))
        self.assertLessEqual(len(observed), limit)
        return result

    def test_a_pass_on_the_second_miss_can_rescue_a_candidate(self):
        scores = {'inc': (False, False, True), 'a': (False, False, True), 'b': (False, True, True)}
        self.assertEqual(self.choose(scores, 9, recheck=True).prompt, 'b')

    def test_exhaustive_binary_panels_preserve_strict_gain_and_critical_pass(self):
        for triple in product(product((False, True), repeat=3), repeat=3):
            scores = dict(zip(('inc', 'a', 'b'), triple, strict=True))
            for limit, recheck in product((3, 5, 7, 9), (False, True)):
                selected = self.choose(scores, limit, recheck).prompt
                if selected != 'inc':
                    self.assertGreater(sum(scores[selected]), sum(scores['inc']))
                    self.assertTrue(not scores['inc'][2] or scores[selected][2])
