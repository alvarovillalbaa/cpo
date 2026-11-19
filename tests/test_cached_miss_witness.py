import unittest

from benchmarks.cached_miss_witness import choose_witness
from cpo import Row


class CachedMissWitnessTests(unittest.TestCase):
    def test_uses_only_current_rows_with_an_observed_incumbent_failure(self):
        rows = [Row('unknown', 'task'), Row('winner', 'task'), Row('miss', 'task')]
        paid = {'unknown': {'other': True}, 'winner': {'inc': True, 'other': True},
                'miss': {'inc': False, 'other': True}, 'excluded': {'inc': False, 'other': True}}
        self.assertIs(choose_witness('inc', rows, paid, 'one-prior-pass'), rows[2])
        self.assertIsNone(choose_witness('other', rows, paid, 'one-prior-pass'))

    def test_threshold_and_seeded_ties(self):
        rows = [Row('a', 'task'), Row('b', 'task')]
        paid = {'a': {'inc': False, 'other': True}, 'b': {'inc': False, 'other': True}}
        self.assertIs(choose_witness('inc', rows, paid, 'one-prior-pass'), rows[0])
        self.assertIsNone(choose_witness('inc', rows, paid, 'two-prior-passes'))
        self.assertIsNone(choose_witness('inc', rows, paid, 'seeded'))
        paid['b']['another'] = True
        self.assertIs(choose_witness('inc', rows, paid, 'two-prior-passes'), rows[1])

    def test_unproductive_known_miss_is_only_used_by_the_cost_control(self):
        rows = [Row('empty', 'task'), Row('miss', 'task')]
        paid = {'miss': {'inc': False, 'first': False, 'second': False}}
        self.assertIs(choose_witness('inc', rows, paid, 'known-miss'), rows[1])
        self.assertIsNone(choose_witness('inc', rows, paid, 'one-prior-pass'))
