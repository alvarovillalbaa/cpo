import unittest

from benchmarks import prompteval_subject_history as history


class SubjectHistoryTests(unittest.TestCase):
    def test_history_reads_only_selected_cases_and_charges_each_model_separately(self):
        class SelectedCases(str):
            def __getitem__(self, case):
                if case == 0:
                    raise AssertionError('The profile read an excluded source case')
                return super().__getitem__(case)

        data = {'panels': [
            {'subject': 'source', 'model': 'a', 'correctness': list(map(SelectedCases, ('011111111', '000001111')))},
            {'subject': 'source', 'model': 'b', 'correctness': list(map(SelectedCases, ('000001111', '011111111')))},
        ]}
        profiles = history.make_profiles(data, {'source': list(range(1, 9))}, ['a', 'b'])
        self.assertEqual(profiles['a'][4]['scores'], {'0': 4, '1': 0})
        self.assertEqual(profiles['b'][4]['scores'], {'0': 0, '1': 4})
        self.assertEqual(profiles['a'][8]['evaluations'], 16)
        self.assertEqual(profiles['b'][4]['evaluations'], 8)

    def test_source_likely_challenger_still_needs_complete_target_validation(self):
        trial = {'seed': 1, 'candidates': ['0', '1', '2'], 'train': [0, 1], 'validation': [2, 3]}
        plan = {'evaluationLookupLimit': 6, 'challengeWidth': 1}
        profile = {'scores': {'0': 0, '1': 4, '2': 1}}
        result = history.evaluate(history.PRIMARY, profile, ['00101', '00011', '00111'], trial, [4], plan)
        self.assertEqual(result['candidate'], '0')
        with self.assertRaisesRegex(ValueError, 'must be separate'):
            history.evaluate(history.PRIMARY, profile, ['00101', '00011', '00111'], trial, [3], plan)

    def test_charged_comparison_includes_profile_cost(self):
        totals = {'history': {'evaluations': 7, 'allocatedSourceLookups': 3, 'holdoutPasses': 2},
                  'cold': {'evaluations': 9, 'allocatedSourceLookups': 0, 'holdoutPasses': 1}}
        self.assertEqual(history.charged_comparison(totals, 'history', 'cold'),
                         {'passDelta': 1, 'chargedLookupDelta': 1, 'qualified': False})
