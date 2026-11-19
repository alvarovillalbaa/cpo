import unittest

from benchmarks.recorded_archive_first import ArchiveCheck, account_fallback, check_archive, recorded_decision
from cpo import Row


class ArchiveFirstTests(unittest.TestCase):
    def setUp(self):
        self.rows = tuple(Row(case, 'task', case == 'critical') for case in ('critical', 'one', 'two'))

    def test_first_qualified_prompt_skips_later_retrievals(self):
        paid = []
        outcomes = {'old': {'critical'}, 'regresses': {'one', 'two'}, 'qualified': {'critical', 'one'}}

        def evaluate(prompt, row):
            paid.append((prompt, row.id))
            return row.id in outcomes[prompt]

        result = check_archive('old', ('regresses', 'qualified', 'never'), self.rows, evaluate)
        self.assertEqual((result.selected, result.retrieved), ('qualified', 2))
        self.assertEqual(result.evaluations, len(set(paid)))
        self.assertNotIn(('qualified', 'two'), paid)
        self.assertEqual(result.evidence['regresses'], {'critical': False})

    def test_full_gate_resumes_the_same_candidate_before_trying_another(self):
        outcomes = {'old': {'critical'}, 'partial': {'critical', 'one'}, 'complete': {'critical', 'one', 'two'}}
        result = check_archive('old', ('partial', 'complete'), self.rows,
                               lambda prompt, row: row.id in outcomes[prompt], require_full=True)
        self.assertEqual(result.selected, 'complete')
        self.assertEqual(result.evidence['partial'], {'critical': True, 'one': True, 'two': False})
        self.assertEqual(result.evaluations, 9)

    def test_fallback_charges_only_unique_paired_observations(self):
        check = ArchiveCheck(None, {'old': {'critical': True, 'one': False, 'two': False},
                                    'archive': {'critical': False}, 'different': {'one': False}}, 2)
        original = {'qualificationEvaluations': 4, 'challenger': 'archive', 'qualification': {'critical': False}}
        self.assertEqual(account_fallback('old', self.rows, check, original), 5)
        original['qualificationEvaluations'] = 0
        self.assertEqual(account_fallback('old', self.rows, check, original), 5)

    def test_archive_acceptance_still_charges_a_paid_validation_screen(self):
        check = ArchiveCheck('saved', {'old': {'promotion': False}, 'saved': {'promotion': True}}, 1)
        matrix = {'saved': {'holdout': (True, 1)}}
        result = recorded_decision({}, 'saved', check, 2, matrix, ['holdout'], paid_validation=3)
        self.assertEqual(result['calls'], 6)
        self.assertEqual(result['searchEvaluations'], 3)
        self.assertEqual(result['proposalSlots'], 1)
