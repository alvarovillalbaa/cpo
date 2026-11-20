import unittest

from benchmarks.recorded_math_validation_ties import run_trial


class RecordedMathValidationTieTests(unittest.TestCase):
    def test_completed_tie_needs_separate_qualification(self):
        cohorts = ([0], [1, 2, 3], [4, 5], [6, 7])
        old = (0, 0, 1, 1, 0, 1, 0, 1)
        for positive in (True, False):
            new = (0, 1, 0, 1, int(positive), 1, 1, 1)
            cells = {p: [(bit, None, False) for bit in values] for p, values in (('old', old), ('new', new))}
            strict, _, _ = run_trial(cells, 'old', ('new',), cohorts, 0, 'strict', 12)
            tied, decision, _ = run_trial(cells, 'old', ('new',), cohorts, 0, 'finish-four', 12)
            self.assertEqual(strict['holdoutPasses'], 1)
            self.assertEqual(tied['tieNominations'], 1)
            self.assertEqual(tied['tiePromotions'], int(positive))
            self.assertEqual(tied['holdoutPasses'], 1 + int(positive))
            self.assertEqual(decision[3], 'new' if positive else 'old')
            self.assertEqual(tied['searchLookups'], strict['searchLookups'] + 1)
            self.assertNotIn('historicalCostNanodollars', tied)

    def test_strict_winner_and_historical_accounting_reproduce(self):
        rows = ([0], [1, 2, 3], [4, 5], [6, 7])
        old, new = (0, 0, 1, 1, 0, 1, 0, 1), (0, 1, 1, 1, 1, 1, 1, 1)
        cells = {p: [(bit, 7, True) for bit in values] for p, values in (('old', old), ('new', new))}
        baseline = run_trial(cells, 'old', ('new',), rows, 0, 'strict', 12)
        extended = run_trial(cells, 'old', ('new',), rows, 0, 'finish-four', 12)
        self.assertEqual(baseline, extended)
        self.assertEqual(extended[0]['historicalCostNanodollars'], 7 * extended[0]['paidLookups'])
        self.assertEqual(extended[0]['historicalErrors'], extended[0]['paidLookups'])
