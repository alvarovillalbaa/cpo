from collections import Counter
from itertools import product
import unittest

from benchmarks.balanced_finalist_race import balanced_screen
from benchmarks.finalist_score_bounds import select_by_bounds
from cpo import Observation, Row


class FinalistScoreBoundTests(unittest.TestCase):
    def test_exact_winner_and_critical_guard_over_every_small_matrix(self):
        rows = tuple(Row(str(i), 'task', i == 2) for i in range(4))
        incumbent, candidates = 'incumbent', ('one', 'two')
        keys = [(prompt, row.id) for prompt in (incumbent, *candidates) for row in rows]
        settings = {'metric_limit': 12, 'width': 2, 'screen_rows': 2}
        for matrix in product((False, True), repeat=len(keys)):
            answers = dict(zip(keys, matrix, strict=True))
            expected = balanced_screen(
                incumbent, candidates, rows, lambda p, row: Observation(answers[p, row.id], {}), **settings)
            for defer in (False, True):
                lookups, audit = set(), Counter()

                def evaluate(prompt, row):
                    key = (prompt, row.id)
                    self.assertNotIn(key, lookups)
                    lookups.add(key)
                    return Observation(answers[key], {})

                measured = select_by_bounds(incumbent, candidates, rows, evaluate, defer_incumbent=defer,
                                            audit=audit, **settings)
                self.assertEqual(measured.prompt, expected.prompt)
                self.assertEqual(measured.finalist, expected.finalist)
                self.assertEqual(measured.evaluations, len(lookups))
                self.assertEqual(measured.evaluations, sum(audit.values()))
                self.assertLessEqual(measured.evaluations, settings['metric_limit'])
