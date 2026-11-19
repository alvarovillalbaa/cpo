from collections import Counter
import unittest

from benchmarks.prompteval_finalist_retry import retry_finalist
from cpo import Observation, Row


class FinalistRetryTests(unittest.TestCase):
    def run_policy(self, outcomes, policy, *, cap=18):
        calls = []
        audit = Counter()
        rows = tuple(Row(case, 'task') for case in ('a', 'b', 'miss', 'other', 'last'))

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(row.id in outcomes[prompt], {})

        result = retry_finalist('old', tuple(key for key in outcomes if key != 'old'), rows, evaluate,
                                metric_limit=cap, policy=policy, audit=audit)
        self.assertEqual(len(calls), result.evaluations)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertLessEqual(len(calls), cap)
        return result, calls, audit

    def test_rotating_the_witness_can_certify_a_candidate_screened_out_on_the_first(self):
        outcomes = {'old': {'a', 'b'}, 'backup': {'a', 'b', 'other'}, 'first': {'miss'}}
        same, _, _ = self.run_policy(outcomes, 'same-miss')
        rotated, _, audit = self.run_policy(outcomes, 'next-miss')
        self.assertEqual(same.prompt, 'old')
        self.assertEqual(rotated.prompt, 'backup')
        self.assertEqual(audit['retryCertificate.promote'], 1)

    def test_a_successful_first_certificate_skips_retry(self):
        outcomes = {'old': {'a', 'b'}, 'first': {'a', 'b', 'miss'}, 'later': {'other'}}
        result, calls, audit = self.run_policy(outcomes, 'next-miss')
        self.assertEqual(result.prompt, 'first')
        self.assertTrue(all(prompt != 'later' for prompt, _ in calls))
        self.assertEqual(audit['additionalLookups'], 0)

    def test_lookup_caps_apply_even_when_no_candidate_passes(self):
        outcomes = {'old': {'a', 'b'}, **{str(i): set() for i in range(12)}}
        result, _, audit = self.run_policy(outcomes, 'next-miss-at-most-eight', cap=40)
        self.assertEqual(result.prompt, 'old')
        self.assertEqual(audit['additionalLookups'], 8)
        result, _, audit = self.run_policy(outcomes, 'next-miss-at-most-eight', cap=18)
        self.assertEqual(result.evaluations, 18)
        self.assertEqual(audit['additionalLookups'], 4)
