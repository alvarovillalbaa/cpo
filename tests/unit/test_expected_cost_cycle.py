from unittest import TestCase

from cpo import Observation, Row
from cpo.expected_cost_cycle import run_expected_cost_fixed_pool_cycle
from cpo.expected_qualification import certify_expected_qualification
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


class ExpectedCostCycleTests(TestCase):
    def setUp(self):
        self.validation = tuple(Row(str(i), 'validation') for i in range(4))
        self.qualification = tuple(Row(f'q{i}', str(i // 4)) for i in range(8))

    def validate(self, prompt, row):
        return Observation(prompt == 'new' or row.id == '1', {})

    def qualify(self, prompt, row, repeat):
        return prompt == 'new'

    def run_ordered(self, qualify=None, **options):
        return run_expected_cost_fixed_pool_cycle(
            'old', ('new',), iter(self.validation), iter(self.qualification), self.validate,
            metric_limit=30, qualify=self.qualify if qualify is None else qualify, **options,
        )

    def run_seeded(self, qualify=None, **options):
        return run_fixed_pool_cycle(
            'old', ('new',), self.validation, self.qualification, self.validate,
            metric_limit=30, qualify=self.qualify if qualify is None else qualify, **options,
        )

    def test_reproduce_scheduler_from_observed_validation(self):
        validation, qualification = {}, []
        original_validate = self.validate

        def observe(prompt, row):
            reply = original_validate(prompt, row)
            validation.setdefault(prompt, {})[row.id] = reply.passed
            return reply

        def qualify(prompt, row, repeat):
            qualification.append((prompt, row.id, repeat))
            return self.qualify(prompt, row, repeat)

        seeded = self.run_seeded(seed=17)
        self.validate = observe
        result = self.run_ordered(qualify, seed=17)
        validation_counts = tuple((sum(validation[p].values()), len(validation[p])) for p in ('old', 'new'))
        expected = certify_expected_qualification(
            'old', 'new', self.qualification, self.qualify, validation_counts=validation_counts, seed=17,
        )
        self.assertEqual(result.search, seeded.search)
        self.assertEqual(result.qualification, expected)
        self.assertEqual(result.prompt, seeded.prompt)
        self.assertEqual(result.qualification_evaluations, len(qualification))
        self.assertEqual(qualification, [(r.prompt, r.row_id, r.repeat) for r in expected.observations])

    def test_partial_caps_preserve_the_seeded_decision_and_prefix(self):
        for limit in range(16):
            with self.subTest(limit=limit):
                result = self.run_ordered(seed=29, qualification_limit=limit)
                self.assertEqual(result, self.run_seeded(seed=29, qualification_limit=limit))

    def test_full_cap_admits_expected_cost_order(self):
        self.assertEqual(self.run_ordered(qualification_limit=16), self.run_ordered())

    def test_repeats_and_critical_regression_use_exact_seeded_gate(self):
        self.qualification = (Row('critical', 'family', critical=True), Row('repair', 'family'))

        def qualify(prompt, row, repeat):
            return (prompt == 'old') == row.critical

        result = self.run_ordered(qualify, repeats=2)
        self.assertEqual(result, self.run_seeded(qualify, repeats=2))
        self.assertEqual(result.prompt, 'old')

    def test_no_nominee_dispatches_no_qualification(self):
        self.validate = lambda *_: Observation(True, {})
        result = self.run_ordered(lambda *_: self.fail('No qualification can run without a nominee'))
        self.assertEqual(result.prompt, 'old')
        self.assertIsNone(result.qualification)

    def test_invalid_cap_and_overlapping_panels_reject_before_search(self):
        self.validate = lambda *_: self.fail('Invalid options must reject before spending')
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            self.run_ordered(qualification_limit=False)
        self.qualification = self.validation
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            self.run_ordered()
