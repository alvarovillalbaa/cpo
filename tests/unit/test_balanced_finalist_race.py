import unittest

from benchmarks.balanced_finalist_race import balanced_screen, matched_prefix
from cpo import Observation, Row


class BalancedFinalistRaceTests(unittest.TestCase):
    def test_screen_pairs_a_miss_with_a_pass_and_preserves_the_order_of_other_rows(self):
        rows = [Row(str(i), 'task') for i in range(4)]
        outcomes = dict(zip((row.id for row in rows), (True, True, False, False), strict=True))
        self.assertEqual([row.id for row in matched_prefix(rows, outcomes, 2)], ['2', '0', '1', '3'])
        self.assertEqual(matched_prefix(rows, dict.fromkeys(outcomes, False), 2), rows)

    def test_selects_best_exact_finalist_and_charges_the_incumbent_once(self):
        rows = [Row(str(i), 'task', i == 1) for i in range(4)]
        scores = {'base': '1100', 'first': '1110', 'better': '1111', 'third': '0111'}
        seen = set()

        def evaluate(prompt, row):
            key = (prompt, row.id)
            self.assertNotIn(key, seen)
            seen.add(key)
            return Observation(scores[prompt][int(row.id)] == '1', {})

        result = balanced_screen('base', ('first', 'better', 'third'), rows, evaluate,
                                 metric_limit=14, width=3, screen_rows=2)
        self.assertEqual(result.prompt, 'better')
        self.assertEqual(result.evaluations, len(seen))
        self.assertLessEqual(result.evaluations, 14)
        with self.assertRaises(ValueError):
            balanced_screen('base', ('first', 'better', 'third'), rows, lambda *_: self.fail('lookup before budget check'),
                            metric_limit=13, width=3, screen_rows=2)
