from collections import Counter
from functools import partial
from unittest import TestCase

from benchmarks import complementary_backup as backup
from benchmarks import finalist_screen_budget as original
from cpo import Observation, Row


class ComplementaryBackupTests(TestCase):
    def race(self, selector, *, cap, protect_last=False, primary='10010'):
        outcomes = {'incumbent': '00011', 'primary': primary, 'backup': '00011', 'alternate': '01110'}
        rows = tuple(Row(str(case), 'task', protect_last and case == 4) for case in range(5))
        journal = {}

        def evaluate(prompt, row):
            key = (prompt, row.id)
            self.assertNotIn(key, journal)
            self.assertLess(len(journal), cap)
            passed = outcomes[prompt][int(row.id)] == '1'
            journal[key] = passed
            return Observation(passed, {})

        result = selector('incumbent', tuple(outcomes)[1:], rows, evaluate, metric_limit=cap,
                          width=3, screen_rows=2, mode='try-backup', audit=Counter())
        self.assertEqual(result.evaluations, len(journal))
        return result, journal

    def test_witness_breaks_the_tie_and_reuses_the_probe(self):
        control, _ = self.race(original.screen, cap=18)
        selected, journal = self.race(partial(backup.screen, complementary=True), cap=18)
        self.assertEqual(control.prompt, 'incumbent')
        self.assertEqual(selected.prompt, 'alternate')
        self.assertEqual(sum(prompt == 'alternate' for prompt, _ in journal), 5)

    def test_keep_original_budget_and_critical_protection(self):
        select = partial(backup.screen, complementary=True)
        self.assertEqual(self.race(select, cap=17)[0].prompt, 'incumbent')
        self.assertEqual(self.race(select, cap=18, protect_last=True)[0].prompt, 'incumbent')

    def test_primary_success_preserves_original_journal(self):
        primary = '11111'
        control = self.race(original.screen, cap=18, primary=primary)
        self.assertEqual(control[0].prompt, 'primary')
        for complementary in (False, True):
            with self.subTest(complementary=complementary):
                select = partial(backup.screen, complementary=complementary)
                self.assertEqual(self.race(select, cap=18, primary=primary), control)
