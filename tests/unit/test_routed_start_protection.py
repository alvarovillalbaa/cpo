from itertools import product
import unittest

from benchmarks.routed_start_protection import halves, qualify_archive_halves
from cpo import Row
from cpo.paired_qualification import certify_paired_qualification


class RoutedStartProtectionTests(unittest.TestCase):
    def test_fresh_and_archive_proofs_match_the_full_two_half_gate(self):
        cases = tuple(range(4))
        rows = halves(Row(str(case), 'validation') for case in cases)
        for outcomes in product((False, True), repeat=2 * len(cases)):
            matrix = {'old': outcomes[:len(cases)], 'new': outcomes[len(cases):]}
            gains = [sum(matrix['new'][i] - matrix['old'][i] for i in group)
                     for group in ((0, 1), (2, 3))]
            expected = min(gains) >= 0 and sum(gains) > 0

            def evaluate(prompt, case):
                return matrix[prompt][case]

            archived, calls, evidence = qualify_archive_halves('old', 'new', cases, evaluate)
            fresh = certify_paired_qualification('old', 'new', rows,
                                                 lambda p, row, _: evaluate(p, int(row.id)))
            self.assertEqual(archived, expected)
            self.assertEqual(fresh.status == 'promoted', expected)
            self.assertEqual(len(evidence), len(cases) + calls)
            self.assertEqual(len(set((p, case) for p, case, _ in evidence)), len(evidence))
            self.assertLessEqual(len(fresh.observations), 2 * len(cases))

    def test_fresh_half_labels_keep_critical_cases_protected(self):
        rows = halves(Row(str(i), 'validation', critical=i == 1) for i in range(4))
        matrix = {'old': (False, True, False, False), 'new': (True, False, True, True)}
        decision = certify_paired_qualification('old', 'new', rows,
                                                lambda p, row, _: matrix[p][int(row.id)])
        self.assertEqual(decision.status, 'rejected')
