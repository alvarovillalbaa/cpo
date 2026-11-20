from collections import Counter
from itertools import product
import unittest

from benchmarks.finalist_witness_rescue import rescue
from cpo import Observation, Row


ROWS = tuple(Row(str(i), 'task', critical=i == 1) for i in range(4))


def select(matrix, cap, triggers, **kwargs):
    calls, audit = set(), Counter()

    def evaluate(prompt, row):
        key = (prompt, row.id)
        if key in calls:
            raise AssertionError('Search charged one reply twice')
        calls.add(key)
        return Observation(matrix[prompt][int(row.id)] == '1', {})

    result = rescue('base', ('a', 'b'), ROWS, evaluate, metric_limit=cap, triggers=triggers, audit=audit, **kwargs)
    return result, len(calls), audit


class FinalistWitnessRescueTests(unittest.TestCase):
    def test_rescue_after_empty_or_rejected_narrow_search(self):
        empty = {'base': '0101', 'a': '0011', 'b': '0111'}
        rejected = {'base': '0101', 'a': '1010', 'b': '0111'}
        for trigger, matrix in (('empty', empty), ('rejected', rejected)):
            with self.subTest(trigger=trigger):
                opening, _, _ = select(matrix, 12, ())
                self.assertEqual(opening.prompt, 'base')
                chosen, paid, audit = select(matrix, 12, (trigger,))
                self.assertEqual(chosen.prompt, 'b')
                self.assertEqual(audit['rescuedNominees'], 1)
                self.assertEqual(chosen.evaluations, paid)

    def test_every_returned_candidate_has_strict_gain_under_the_cap(self):
        choices = [''.join(bits) for bits in product('01', repeat=len(ROWS))]
        for base, a, b in product(choices, repeat=3):
            matrix = {'base': base, 'a': a, 'b': b}
            for cap in (8, 12):
                result, paid, audit = select(matrix, cap, ('empty', 'rejected'))
                self.assertEqual(result.evaluations, paid)
                self.assertLessEqual(paid, cap)
                self.assertLessEqual(audit['rescueProofs'], 2)
                if result.prompt != 'base':
                    winner = matrix[result.prompt]
                    self.assertGreater(winner.count('1'), base.count('1'))
                    self.assertGreaterEqual(winner[1], base[1])

    def test_probe_limit_keeps_unmeasured_witnesses_out_of_the_race(self):
        matrix = {'base': '0101', 'a': '0100', 'b': '0111'}
        denied, _, audit = select(matrix, 12, ('empty',), stop_at_witness=True, probe_limit=1)
        self.assertEqual(denied.prompt, 'base')
        self.assertEqual(audit['rescueProbes'], 1)
        admitted, _, audit = select(matrix, 12, ('empty',), stop_at_witness=True, probe_limit=2)
        self.assertEqual(admitted.prompt, 'b')
        self.assertEqual(audit['rescueProbes'], 2)
