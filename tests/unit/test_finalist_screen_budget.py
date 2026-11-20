from collections import Counter
from itertools import product
import unittest

from benchmarks.balanced_finalist_race import balanced_screen
from benchmarks.finalist_screen_budget import screen, shortlist
from cpo import Observation, Row


class FinalistScreenBudgetTests(unittest.TestCase):
    def test_lazy_screen_preserves_rank_on_every_binary_probe_matrix(self):
        prompts = tuple(str(i) for i in range(6))
        rows = (Row('0', 'task'), Row('1', 'task'))
        for outcomes in product((False, True), repeat=12):
            for size in (1, 2):
                seen = []

                def observe(prompt, row):
                    seen.append((prompt, row.id))
                    return Observation(outcomes[2 * int(prompt) + int(row.id)], {})

                expected = shortlist(prompts, rows, observe, size=size, lazy=False)
                seen.clear()
                actual = shortlist(prompts, rows, observe, size=size, lazy=True)
                self.assertEqual(actual, expected)
                self.assertEqual(len(seen), len(set(seen)))
                self.assertLessEqual(len(seen), 12)

    def test_shortlist_proof_keeps_the_exact_protected_validation_winner(self):
        rows = tuple(Row(str(i), 'task', i == 1) for i in range(4))
        prompts = ('a', 'b', 'c', 'd')
        matrix = {'base': '1100', 'a': '1011', 'b': '1110', 'c': '1111', 'd': '1111'}
        settings = {'metric_limit': 16, 'width': 4, 'screen_rows': 2}

        def evaluate(prompt, row):
            return Observation(matrix[prompt][int(row.id)] == '1', {})

        original = balanced_screen('base', prompts, rows, evaluate, **settings)
        for mode in ('two-lazy', 'two-lazy-bounds'):
            observed = screen('base', prompts, rows, evaluate, mode=mode, audit=Counter(), **settings)
            self.assertEqual(observed.prompt, original.prompt)
            self.assertLess(observed.evaluations, original.evaluations)
        audit = Counter()
        observed = screen('base', prompts, rows, evaluate, mode='try-backup', audit=audit, **settings)
        self.assertEqual(observed.prompt, original.prompt)
        self.assertEqual(audit['backupRaces'], 1)
        self.assertLessEqual(observed.evaluations, settings['metric_limit'])
