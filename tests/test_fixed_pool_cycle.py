import unittest

from cpo import Observation, Row
from cpo.fixed_pool_cycle import run_fixed_pool_cycle


class FixedPoolCycleTests(unittest.TestCase):
    validation = (Row('retained', 'task'), Row('miss', 'task'))
    qualification = (Row('q1', 'task'), Row('q2', 'task'))

    def evaluate(self, prompt, row):
        return Observation(prompt == 'new' or row.id == 'retained', {})

    def test_search_and_qualification_are_verified_before_dispatch(self):
        def unexpected(*_):
            self.fail('Invalid cohorts or configuration must be rejected before evaluation')

        for rows, options in ((self.validation, {}), (self.qualification, {'qualification_limit': -1}),
                              (self.qualification, {'screen': 'unknown'})):
            with self.subTest(options=options), self.assertRaises(ValueError):
                run_fixed_pool_cycle('old', ['new'], self.validation, rows, unexpected,
                                     metric_limit=4, qualify=unexpected, **options)

    def test_candidate_can_be_promoted_after_a_sufficient_prefix(self):
        requests = []

        def qualify(prompt, row, repeat):
            requests.append((prompt, row.id, repeat))
            return prompt == 'new'

        result = run_fixed_pool_cycle('old', ['new'], self.validation, self.qualification, self.evaluate,
                                      metric_limit=4, qualify=qualify)
        self.assertEqual((result.prompt, result.search.prompt, result.promoted), ('new', 'new', True))
        self.assertEqual(result.search.evaluations, 4)
        self.assertEqual(result.qualification_evaluations, len(requests))
        self.assertEqual(len(requests), 3)

    def test_an_unfinished_qualification_keeps_the_incumbent_and_observed_reply(self):
        result = run_fixed_pool_cycle('old', ['new'], self.validation, self.qualification, self.evaluate,
                                      metric_limit=4, qualify=lambda prompt, *_: prompt == 'new',
                                      qualification_limit=1)
        self.assertEqual((result.prompt, result.search.prompt, result.promoted), ('old', 'new', False))
        self.assertEqual(result.qualification.status, 'undecided')
        self.assertEqual(result.qualification_evaluations, 1)

    def test_no_certified_challenger_spends_no_qualification_calls(self):
        def unexpected(*_):
            self.fail('Qualification requires a certified challenger')

        result = run_fixed_pool_cycle('old', ['blocked'], self.validation, self.qualification, self.evaluate,
                                      metric_limit=4, qualify=unexpected)
        self.assertEqual(result.prompt, 'old')
        self.assertIsNone(result.qualification)
        self.assertEqual(result.qualification_evaluations, 0)

    def test_qualification_rejects_a_critical_or_family_loss_despite_a_total_gain(self):
        for critical in (True, False):
            family = 'task' if critical else 'protected-family'
            rows = (Row('lost', family, critical), *self.qualification)

            def qualify(prompt, row, _repeat):
                return (prompt == 'old') == (row.id == 'lost')

            with self.subTest(critical=critical):
                result = run_fixed_pool_cycle('old', ['new'], self.validation, rows, self.evaluate,
                                              metric_limit=4, qualify=qualify)
                self.assertEqual(result.prompt, 'old')
                self.assertEqual(result.qualification.status, 'rejected')

    def test_two_read_screen_reuses_the_same_independent_gate(self):
        rows = (*self.validation, Row('another-miss', 'task'))
        outcomes = {'old': {'retained'}, 'blocked': set(), 'new': {'retained', 'another-miss'}}
        result = run_fixed_pool_cycle(
            'old', ['blocked', 'new'], rows, self.qualification,
            lambda prompt, row: Observation(row.id in outcomes[prompt], {}),
            metric_limit=7, qualify=lambda prompt, *_: prompt == 'new', screen='bounded-two-reads',
        )
        self.assertEqual((result.prompt, result.search.finalist), ('new', 'new'))
        self.assertEqual(result.search.evaluations, 7)
