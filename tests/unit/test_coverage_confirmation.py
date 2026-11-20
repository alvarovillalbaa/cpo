"""T2 checks over small synthetic validation panels."""

from itertools import product
import unittest

from cpo.coverage_confirmation import confirm_covered_gain


class CoverageConfirmationTests(unittest.TestCase):
    def test_matches_exhaustive_gate_for_partial_and_full_evidence(self):
        rows = ('a', 'b', 'c', 'd')
        strata = {'a': 'x', 'b': 'x', 'c': 'y'}
        for initial in product((False, True), repeat=len(rows)):
            baseline = dict(zip(rows, initial))
            protected = {row for row in strata if baseline[row]}
            for response in product((False, True), repeat=len(rows)):
                candidate = dict(zip(rows, response))
                eligible = (all(candidate[row] for row in protected)
                            and (candidate['a'] or candidate['b']) and candidate['c'])
                for target in range(sum(initial), len(rows) + 1):
                    expected = sum(response) if eligible and sum(response) > target else None
                    for known_rows in ((), ('a', 'd'), ('c',), rows):
                        known = {row: candidate[row] for row in known_rows}
                        for prioritize in (False, True):
                            reads = set()

                            def evaluate(row):
                                self.assertNotIn(row, known)
                                self.assertNotIn(row, reads)
                                reads.add(row)
                                return candidate[row]

                            self.assertEqual(confirm_covered_gain(
                                baseline, target, protected, strata, known, evaluate,
                                prioritize_coverage=prioritize,
                            ), expected)

    def test_coverage_failure_uses_only_remaining_witnesses(self):
        baseline = dict.fromkeys(('ordinary', 'observed', 'last'), False)
        strata = {'observed': 'risk', 'last': 'risk'}
        reads = []

        def evaluate(row):
            reads.append(row)
            return row == 'ordinary'

        self.assertIsNone(confirm_covered_gain(
            baseline, 0, (), strata, {'observed': False}, evaluate,
        ))
        self.assertEqual(reads, ['last'])
        reads.clear()
        self.assertIsNone(confirm_covered_gain(
            baseline, 0, (), strata, {'observed': False, 'last': False}, evaluate,
        ))
        self.assertEqual(reads, [])

    def test_protected_row_failure_precedes_coverage_checks(self):
        baseline = {'covered': False, 'protected': True}
        reads = []

        def evaluate(row):
            reads.append(row)
            return False

        self.assertIsNone(confirm_covered_gain(
            baseline, 0, {'protected'}, {'covered': 'risk'}, {}, evaluate,
        ))
        self.assertEqual(reads, ['protected'])
