from collections import Counter
from itertools import product
import unittest

from benchmarks.routed_witness_split import routed_selection
from cpo import Observation, Row


ROWS = tuple(Row(str(i), 'task', critical=i == 2) for i in range(4))


def select(matrix, cap, mode, **kwargs):
    measured, audit = [], Counter()

    def evaluate(prompt, row):
        measured.append((prompt, row.id))
        return Observation(matrix[prompt][int(row.id)] == '1', {})

    result = routed_selection('base', ('a', 'b'), ROWS, evaluate, metric_limit=cap,
                              mode=mode, split=True, discovery=False, audit=audit, **kwargs)
    return result, measured, audit


class RoutedWitnessSplitTests(unittest.TestCase):
    def test_retry_uses_the_other_miss_after_a_rejected_proof(self):
        matrix = {'base': '0011', 'a': '1001', 'b': '0111'}
        first, _, _ = select(matrix, 12, 'first')
        self.assertEqual(first.prompt, 'base')
        retry, measured, audit = select(matrix, 12, 'retry')
        self.assertEqual(retry.prompt, 'b')
        self.assertEqual(audit['proofAttempts'], 2)
        self.assertEqual(audit['secondMissProbes'], 1)
        self.assertEqual(next(case for p, case in measured if p == 'b'), '1')

    def test_dual_race_requires_reserved_capacity_for_the_second_witness(self):
        matrix = {'base': '0011', 'a': '1011', 'b': '1111'}
        restricted, _, audit = select(matrix, 11, 'dual')
        self.assertEqual(restricted.prompt, 'a')
        self.assertEqual(audit['proofAttempts'], 1)
        complete, _, audit = select(matrix, 12, 'dual')
        self.assertEqual(complete.prompt, 'b')
        self.assertEqual(audit['twoWitnessCycles'], 1)

    def test_widening_requires_the_specified_third_outcome_and_reserve(self):
        matrix = {'base': '0011', 'a': '1011', 'b': '0111'}
        for cap, outcome, wide in ((12, True, 1), (12, False, 0), (11, True, 0)):
            result, measured, audit = select(matrix, cap, 'retry', widen_on=outcome)
            self.assertEqual(audit['balancedCycles'], wide)
            self.assertEqual(result.evaluations, len(set(measured)))
            self.assertLessEqual(len(measured), cap)

    def test_exact_gain_critical_protection_and_single_charge(self):
        scores = [''.join(bits) for bits in product('01', repeat=len(ROWS))]
        for base, a, b in product(scores, repeat=3):
            matrix = {'base': base, 'a': a, 'b': b}
            for mode, cap in product(('first', 'retry', 'dual'), (8, 12)):
                result, measured, audit = select(matrix, cap, mode)
                self.assertEqual(result.evaluations, len(measured))
                self.assertEqual(len(measured), len(set(measured)))
                self.assertLessEqual(len(measured), cap)
                self.assertLessEqual(audit['proofAttempts'], 2)
                if result.prompt != 'base':
                    winner = matrix[result.prompt]
                    self.assertGreater(winner.count('1'), base.count('1'))
                    self.assertGreaterEqual(winner[2], base[2])
