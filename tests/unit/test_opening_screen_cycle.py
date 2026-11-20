from unittest import TestCase

from cpo import Observation, ProposalPair, Row
from cpo.opening_screen_cycle import run_opening_screen_cycle


class OpeningScreenCycleTests(TestCase):
    def setUp(self):
        self.train = [Row('train', 'task', fields=2)]
        self.validation = [Row(str(case), 'task', fields=2) for case in range(6)]
        self.holdout = [Row('q0', 'task'), Row('q1', 'task')]
        self.known = {'old': '001100', 'rewrite': '110010', 'repair': '000000'}
        self.search_calls, self.qualification_calls = [], []

    def evaluate(self, prompt, row):
        self.search_calls.append((prompt, row.id))
        passed = self.known[prompt][int(row.id)] == '1'
        return Observation(passed, {}, 2 if passed else 0)

    def qualify(self, prompt, row, repeat):
        self.qualification_calls.append((prompt, row.id, repeat))
        return prompt == 'rewrite'

    def run_cycle(self, **options):
        settings = dict(opening_pair=ProposalPair('rewrite', 'repair'), screen_rows=2, metric_limit=12,
                        qualify=self.qualify, seed=7)
        settings.update(options)
        return run_opening_screen_cycle('old', iter(self.train), iter(self.validation), iter(self.holdout),
                                        self.evaluate, **settings)

    def test_funds_a_complete_pair_and_uses_independent_qualification(self):
        result = self.run_cycle()
        self.assertEqual(result.prompt, 'rewrite')
        self.assertTrue(result.promoted)
        self.assertEqual(result.search.evaluations, 12)
        self.assertEqual(result.search.reflections, 0)
        self.assertEqual(len(self.search_calls), len(set(self.search_calls)))
        self.assertEqual({row for _, row in self.search_calls}, {str(case) for case in range(6)})
        self.assertEqual(result.qualification_evaluations, len(self.qualification_calls))
        self.assertTrue(self.qualification_calls)
        self.assertTrue(all(row.startswith('q') for _, row, _ in self.qualification_calls))

    def test_a_prefix_winner_can_fail_full_validation(self):
        self.known['rewrite'] = '110000'
        result = self.run_cycle()
        self.assertEqual(result.prompt, 'old')
        self.assertFalse(result.search.events[-1]['accepted'])
        self.assertEqual(result.search.evaluations, 12)
        self.assertIsNone(result.qualification)
        self.assertEqual(self.qualification_calls, [])

    def test_full_validation_protects_critical_cases_and_families_outside_the_screen(self):
        for held in (Row('2', 'task', critical=True), Row('2', 'separate-family')):
            with self.subTest(row=held):
                self.validation[2] = held
                result = self.run_cycle()
                self.assertEqual(result.prompt, 'old')
                self.assertFalse(result.search.events[-1]['accepted'])
                self.assertTrue(result.search.events[-1]['critical_loss']
                                or min(result.search.events[-1]['gain_by_family'].values()) < 0)
                self.assertEqual(self.qualification_calls, [])

    def test_field_observations_on_the_suffix_are_validated(self):
        original = self.evaluate

        def invalid(prompt, row):
            if prompt == 'old' and row.id == '5':
                return Observation(False, {}, 2)
            return original(prompt, row)

        self.evaluate = invalid
        with self.assertRaisesRegex(ValueError, 'match the row capacity'):
            self.run_cycle(field_credit=True)
        self.assertEqual(self.qualification_calls, [])

    def test_zero_qualification_allowance_retains_the_incumbent(self):
        result = self.run_cycle(qualification_limit=0)
        self.assertEqual(result.search.prompt, 'rewrite')
        self.assertEqual(result.qualification.status, 'undecided')
        self.assertEqual(result.prompt, 'old')
        self.assertEqual(self.qualification_calls, [])

    def test_perfect_opening_skips_incumbent_suffix_with_same_limited_qualification(self):
        self.known['rewrite'] = '111111'
        oracle = self.run_cycle(qualification_limit=3)
        original_proof = self.qualification_calls.copy()
        self.qualification_calls.clear()
        self.search_calls.clear()
        result = self.run_cycle(qualification_limit=3, certify_opening=True)
        self.assertEqual(result.search.prompt, oracle.search.prompt)
        self.assertEqual(result.qualification, oracle.qualification)
        self.assertEqual(self.qualification_calls, original_proof)
        self.assertEqual(result.search.evaluations, 7)
        self.assertEqual(set(self.search_calls), {('old', '0'), *(('rewrite', row.id) for row in self.validation)})
        self.assertEqual(result.search.events[-1]['kind'], 'certified-full-validation')

    def test_opening_certificate_falls_back_and_protects_critical_suffix(self):
        self.validation[2] = Row('2', 'task', critical=True)
        result = self.run_cycle(qualification_limit=0, certify_opening=True)
        self.assertEqual(result.search.prompt, 'old')
        self.assertEqual(result.search.evaluations, 12)
        self.assertEqual(len(set(self.search_calls)), 12)
        self.assertIsNone(result.qualification)
        self.assertTrue(result.search.events[-1]['critical_loss'])

    def test_full_budget_expected_schedule_keeps_complete_validation(self):
        self.known['rewrite'] = '111111'
        original = self.run_cycle()
        reference = self.search_calls.copy(), self.qualification_calls.copy()
        self.search_calls.clear()
        self.qualification_calls.clear()
        default = self.run_cycle(certify_opening=True)
        self.assertEqual(default, original)
        self.assertEqual((self.search_calls, self.qualification_calls), reference)

    def test_short_panel_uses_its_available_rows(self):
        self.validation = self.validation[:2]
        result = self.run_cycle(screen_rows=8, metric_limit=4)
        self.assertEqual(result.prompt, 'rewrite')
        self.assertEqual(result.search.evaluations, 4)

    def test_invalid_funding_and_overlaps_fail_before_dispatch(self):
        with self.assertRaisesRegex(ValueError, 'fund complete validation'):
            self.run_cycle(metric_limit=11)
        self.holdout = self.validation[:1]
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            self.run_cycle()
        self.assertEqual(self.search_calls, [])
        self.assertEqual(self.qualification_calls, [])
