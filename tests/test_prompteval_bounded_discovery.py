from collections import Counter
import unittest

from cpo import Observation, Row
from cpo.bounded_discovery import select_with_bounded_discovery


class BoundedDiscoveryTests(unittest.TestCase):
    def run_case(self, rows, outcomes, *, discovery=2, prefix=1, cap=20):
        calls = []
        audit = Counter()

        def measure(prompt, row):
            calls.append((prompt, row.id))
            return Observation(row.id in outcomes[prompt], {})

        candidates = tuple(key for key in outcomes if key != 'old')
        result = select_with_bounded_discovery('old', candidates, rows, measure, metric_limit=cap,
                                               discovery_limit=discovery, shared_prefix=prefix, audit=audit)
        self.assertEqual(result.evaluations, len(calls))
        self.assertEqual(len(calls), len(set(calls)))
        self.assertLessEqual(len(calls), cap)
        return result, calls, audit

    def test_fruitless_discovery_stops_reading_the_incumbent_at_the_screen_cap(self):
        rows = tuple(Row(str(index), 'task') for index in range(6))
        outcomes = {'old': {'1', '2', '4', '5'}, **{f'new-{i}': set() for i in range(6)}}
        result, calls, audit = self.run_case(rows, outcomes, cap=20)
        self.assertEqual(result.prompt, 'old')
        self.assertEqual([case for prompt, case in calls if prompt == 'old'], ['0', '1', '2'])
        self.assertEqual(audit['extraIncumbentScreenReads'], 2)

    def test_a_later_challenger_can_gain_on_a_different_miss(self):
        rows = (Row('good', 'task', True), Row('first-miss', 'task'), Row('second-miss', 'task'))
        outcomes = {'old': {'good'}, 'first': set(), 'second': {'good', 'second-miss'}}
        diversified, _, audit = self.run_case(rows, outcomes)
        shared, _, _ = self.run_case(rows, outcomes, prefix=4)
        self.assertEqual(diversified.prompt, 'second')
        self.assertEqual(audit['probesOnOtherMisses'], 1)
        self.assertEqual(shared.prompt, 'old')

    def test_an_extra_witness_does_not_waive_critical_preservation(self):
        rows = (Row('good', 'task', True), Row('first-miss', 'task'), Row('second-miss', 'task'))
        outcomes = {'old': {'good'}, 'first': set(), 'second': {'first-miss', 'second-miss'}}
        result, _, audit = self.run_case(rows, outcomes, cap=7)
        self.assertEqual((result.finalist, result.prompt), ('second', 'old'))
        self.assertEqual(audit['certificate.critical_regression'], 1)
