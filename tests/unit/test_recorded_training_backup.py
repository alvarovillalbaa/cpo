import unittest

from benchmarks.recorded_training_backup import run_trial, strongest_backup
from cpo import Observation, Row


class RecordedTrainingBackupTests(unittest.TestCase):
    def test_backup_reuses_training_incumbent_and_qualifies_once(self):
        cohorts = ([0, 1], [2, 3, 4, 5], [6, 7], [8, 9])
        outcomes = {'old': '0000100101', 'first': '0011101110', 'backup': '1010101111'}
        cells = {prompt: [(int(bit), 3, False) for bit in values] for prompt, values in outcomes.items()}
        before, _, _ = run_trial(cells, 'old', ('backup', 'first'), cohorts, 0, 'training-before', 32)
        backup, trace, _ = run_trial(cells, 'old', ('backup', 'first'), cohorts, 0, 'full-backup', 32)
        self.assertEqual(before['holdoutPasses'], 1)
        self.assertEqual(before['qualificationLookups'], 0)
        self.assertEqual(trace[2:4], ('backup', 'backup'))
        self.assertEqual(backup['holdoutPasses'], 2)
        self.assertEqual(backup['backupPromotions'], 1)
        self.assertEqual(backup['trainingLookups'], 3)
        self.assertLessEqual(backup['qualificationLookups'], 4)
        self.assertEqual(backup['historicalCostNanodollars'], 3 * backup['paidLookups'])

    def test_partial_backup_must_already_prove_gain_and_critical_preservation(self):
        rows = tuple(Row(str(i), 'validation', critical=i == 2) for i in range(5))
        ledger = {('old', row.id): Observation(i == 2, {}) for i, row in enumerate(rows)}
        ledger.update({('valid', '0'): Observation(True, {}), ('valid', '2'): Observation(True, {}),
                       ('unchecked', '0'): Observation(True, {}), ('unchecked', '1'): Observation(True, {}),
                       ('unchecked', '3'): Observation(True, {})})
        roster = ('first', 'unchecked', 'valid')
        self.assertIsNone(strongest_backup('old', 'first', roster, rows, ledger, partial=False))
        self.assertEqual(strongest_backup('old', 'first', roster, rows, ledger, partial=True), 'valid')

    def test_perfect_incumbent_qualification_skips_search(self):
        cohorts = ([0, 1], [2, 3, 4, 5], [6, 7], [8, 9])
        outcomes = {'old': '0000101101', 'first': '0011101110', 'backup': '1010101111'}
        cells = {prompt: [(int(bit), 3, False) for bit in values] for prompt, values in outcomes.items()}
        prior, prior_trace, _ = run_trial(cells, 'old', ('backup', 'first'), cohorts, 0, 'certified-backup', 32)
        checked, trace, _ = run_trial(cells, 'old', ('backup', 'first'), cohorts, 0, 'certified-precheck', 32)
        self.assertEqual(trace[3], prior_trace[3])
        self.assertEqual(checked['holdoutPasses'], prior['holdoutPasses'])
        self.assertEqual(checked['searchLookups'], 0)
        self.assertEqual(checked['paidLookups'], 2)
        self.assertEqual(checked['historicalCostNanodollars'], 6)
