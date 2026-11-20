from collections import Counter
from unittest import TestCase

from benchmarks.bounded_miss_alternation import select
from cpo import Observation, Row


class BoundedMissAlternationTests(TestCase):
    def screen(self, matrix, *, cap, rotate, critical=()):
        rows = tuple(Row(str(case), 'task', case in critical) for case in range(len(matrix['incumbent'])))
        paid, audit = [], Counter()

        def evaluate(prompt, row):
            key = (prompt, row.id)
            self.assertNotIn(key, paid)
            self.assertLess(len(paid), cap)
            paid.append(key)
            return Observation(matrix[prompt][int(row.id)] == '1', {})

        result = select('incumbent', tuple(matrix)[1:], rows, evaluate, metric_limit=cap,
                        audit=audit, alternate=rotate)
        self.assertEqual(result.evaluations, len(paid))
        return result, paid, audit

    def test_alternate_uses_a_different_first_probe_and_proves_full_gain(self):
        matrix = {'incumbent': '0101', 'first': '0000', 'second': '0111'}
        matched, _, _ = self.screen(matrix, cap=9, rotate=False)
        selected, paid, audit = self.screen(matrix, cap=9, rotate=True)
        self.assertEqual(matched.prompt, 'incumbent')
        self.assertEqual(selected.prompt, 'second')
        first_second = next((p, case) for p, case in paid if p == 'second')
        self.assertEqual(first_second, ('second', '2'))
        self.assertEqual(audit['incumbentLookaheadReads'], 2)

    def test_no_scan_beyond_the_two_case_bound(self):
        matrix = {'incumbent': '01101', 'first': '00000', 'second': '00010'}
        selected, paid, audit = self.screen(matrix, cap=11, rotate=True)
        self.assertEqual(selected.prompt, 'incumbent')
        self.assertEqual(audit['incumbentLookaheadReads'], 2)
        self.assertNotIn(('incumbent', '3'), paid)
        self.assertIn(('second', '0'), paid)

    def test_keep_critical_pass_even_when_alternate_witness_passes(self):
        matrix = {'incumbent': '01001', 'first': '00000', 'second': '01110'}
        selected, _, audit = self.screen(matrix, cap=11, rotate=True, critical=(4,))
        self.assertEqual(audit['alternateFinalists'], 1)
        self.assertEqual(selected.prompt, 'incumbent')
