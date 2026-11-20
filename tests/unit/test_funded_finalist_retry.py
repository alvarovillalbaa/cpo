from collections import Counter
from random import Random
from unittest import TestCase

from benchmarks.funded_finalist_retry import retry_finalist
from cpo import Observation, Row
from cpo.lazy_incumbent import select_with_lazy_incumbent


class FundedFinalistRetryTests(TestCase):
    def setUp(self):
        self.rows = [Row(str(i), 'validation') for i in range(4)]
        self.replies = {'start': '0011', 'first': '1000', 'backup': '0111'}

    def run_policy(self, limit, alternate, candidates=('first', 'backup')):
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(self.replies[prompt][int(row.id)] == '1', {})

        audit = Counter()
        result = retry_finalist('start', candidates, self.rows, evaluate, metric_limit=limit,
                                alternate=alternate, audit=audit)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(result.evaluations, len(calls))
        self.assertLessEqual(len(calls), limit)
        return result, audit, calls

    def test_shared_miss_nominates_an_untouched_candidate(self):
        same, _, same_calls = self.run_policy(16, False)
        alternate, audit, calls = self.run_policy(16, True)
        self.assertEqual(same.prompt, 'start')
        self.assertEqual(alternate.prompt, 'backup')
        self.assertEqual(same_calls[-1], ('backup', '0'))
        self.assertEqual([case for prompt, case in calls if prompt == 'backup'][0], '1')
        self.assertEqual(audit['sharedMissScreens'], 1)
        self.assertEqual(audit['validationRescues'], 1)

    def test_retry_requires_full_proof_reserve(self):
        selected, audit, calls = self.run_policy(8, True)
        self.assertEqual(selected.prompt, 'start')
        self.assertEqual(audit['firstFinalistRejections'], 1)
        self.assertEqual(audit['retryScreens'], 0)
        self.assertTrue(all(prompt != 'backup' for prompt, _ in calls))

    def test_exact_gain_and_existing_winner_under_varied_caps(self):
        self.rows[3] = Row('3', 'validation', critical=True)
        rng = Random(127)
        candidates = 'first', 'backup', 'last'
        for _ in range(256):
            self.replies = {prompt: ''.join(rng.choices('01', k=4)) for prompt in ('start', *candidates)}
            limit = rng.randrange(4, 18)
            last = select_with_lazy_incumbent(
                'start', candidates, self.rows, lambda p, r: Observation(self.replies[p][int(r.id)] == '1', {}),
                metric_limit=limit,
            )
            for alternate in (False, True):
                result, audit, _ = self.run_policy(limit, alternate, candidates)
                if last.prompt != 'start':
                    self.assertEqual(result, last)
                    self.assertEqual(audit['retryScreens'], 0)
                if result.prompt != 'start':
                    self.assertGreater(self.replies[result.prompt].count('1'), self.replies['start'].count('1'))
                    if self.replies['start'][3] == '1':
                        self.assertEqual(self.replies[result.prompt][3], '1')
