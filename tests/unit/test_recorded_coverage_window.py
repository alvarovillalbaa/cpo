"""T2 checks for cached screening, exact confirmation, and capped lookup order."""

import unittest

from benchmarks.recorded_coverage_window import screen


class RecordedCoverageWindowTests(unittest.TestCase):
    def test_field_tie_changes_order_without_changing_the_exact_gate(self):
        cases = ('witness', 'other', 'protected')
        strata = {'witness': 'risk', 'other': 'risk', 'protected': 'legacy'}
        outcomes = {
            'initial': ((False, 0), (False, 0), (True, 2)),
            'first': ((False, 0), (True, 2), (True, 2)),
            'second': ((False, 1), (True, 2), (True, 2)),
        }
        for fields, expected in ((False, 'first'), (True, 'second')):
            with self.subTest(fields=fields):
                reads = set()

                def evaluate(prompt, case):
                    self.assertNotIn((prompt, case), reads)
                    reads.add((prompt, case))
                    return outcomes[prompt][cases.index(case)]

                result = screen('initial', ('first', 'second'), cases, strata, evaluate,
                                lambda: len(reads), cap=7, width=4, fields=fields)
                self.assertEqual(result, (expected, 2))
                self.assertEqual(len(reads), 7)
                self.assertTrue(all((expected, case) in reads for case in cases))

    def test_protected_loss_rejects_a_high_ranked_candidate(self):
        cases = ('witness', 'protected')
        successes = {'initial': {'protected'}, 'loss': {'witness'}, 'winner': set(cases)}
        reads = []

        def evaluate(prompt, case):
            reads.append((prompt, case))
            return case in successes[prompt], 2

        outcome = screen('initial', ('loss', 'winner'), cases, {'witness': 'new', 'protected': 'legacy'},
                         evaluate, lambda: len(reads), cap=6, width=4, fields=True)
        self.assertEqual(outcome, ('winner', 2))
        self.assertEqual(len(reads), 6)
        self.assertEqual(len(reads), len(set(reads)))
