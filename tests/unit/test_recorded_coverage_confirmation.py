"""T2 tests for lookup accounting on fixed synthetic matrices."""

import unittest

from benchmarks.recorded_coverage_confirmation import race


class RecordedCoverageRaceTests(unittest.TestCase):
    def test_rejection_can_fund_the_next_complete_confirmation(self):
        validation = ('d', 'a', 'b', 'c')
        strata = {'a': 'x', 'b': 'x', 'c': 'y'}
        successes = {'initial': {'c'}, 'first': {'c', 'd'}, 'second': set(validation)}
        outcomes = {}
        for method in ('late-coverage', 'coverage-first'):
            reads = set()

            def evaluate(prompt, row):
                self.assertNotIn((prompt, row), reads)
                reads.add((prompt, row))
                return row in successes[prompt], 0

            result = race('initial', ['first', 'second'], validation, strata, evaluate, lambda: len(reads),
                          cap=11, method=method)
            outcomes[method] = result, len(reads)
        self.assertEqual(outcomes['late-coverage'], (('initial', 1), 8))
        self.assertEqual(outcomes['coverage-first'], (('second', 2), 11))

    def test_equal_exact_scores_keep_the_earlier_candidate(self):
        validation = ('a', 'b', 'c')
        successes = {'initial': {'a'}, 'first': {'a', 'c'}, 'second': {'a', 'b'}}
        reads = []

        def evaluate(prompt, row):
            reads.append((prompt, row))
            return row in successes[prompt], 0

        for method in ('exact-only', 'late-coverage', 'coverage-first'):
            with self.subTest(method=method):
                reads.clear()
                self.assertEqual(race('initial', ['first', 'second'], validation, {'a': 'x'},
                                      evaluate, lambda: len(reads), cap=9, method=method), ('first', 2))
