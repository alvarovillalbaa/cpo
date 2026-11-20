from itertools import product
import unittest

from benchmarks.recorded_training_corroboration import corroborate, run_trial
from cpo import Observation, Row


class RecordedTrainingCorroborationTests(unittest.TestCase):
    def test_bounded_prefix_agrees_with_exact_training_gain(self):
        rows = (Row('0', 'training'), Row('1', 'training'), Row('2', 'training'))
        for outcomes in product((False, True), repeat=6):
            matrix = {'old': outcomes[:3], 'new': outcomes[3:]}
            for minimum, seed in product((0, 1), (0, 13)):
                calls = []

                def observe(prompt, row):
                    calls.append((prompt, row.id))
                    return Observation(matrix[prompt][int(row.id)], {})

                expected = sum(matrix['new']) - sum(matrix['old']) >= minimum
                supported = corroborate('old', 'new', rows, observe, minimum_gain=minimum, remaining=6, seed=seed)
                self.assertEqual(supported, expected)
                self.assertEqual(len(calls), len(set(calls)))
                self.assertLessEqual(len(calls), 6)
                calls.clear()
                self.assertFalse(corroborate('old', 'new', rows, observe, minimum_gain=minimum, remaining=0, seed=seed))
                self.assertEqual(calls, [])

    def test_training_veto_reuses_the_original_independent_qualification(self):
        cohorts = ([0], [1, 2, 3], [4, 5], [6, 7])
        old, new = (1, 0, 1, 1, 0, 1, 1, 0), (0, 1, 1, 1, 1, 1, 0, 0)
        cells = {p: [(score, 11, False) for score in bits] for p, bits in (('old', old), ('new', new))}
        control, _, _ = run_trial(cells, 'old', ('new',), cohorts, 0, 'strict', 12)
        result, trace, _ = run_trial(cells, 'old', ('new',), cohorts, 0, 'one-gain-nonloss', 12)
        self.assertEqual(result['qualificationLookups'], control['qualificationLookups'])
        self.assertEqual(result['trainingVetoes'], 1)
        self.assertEqual(result['holdoutPasses'], 1)
        self.assertEqual(trace[2:4], ('new', 'old'))
        self.assertEqual(result['historicalCostNanodollars'], 11 * result['paidLookups'])
