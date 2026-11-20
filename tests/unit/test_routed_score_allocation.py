import unittest

from benchmarks.routed_score_allocation import select
from cpo import Observation, Row


class RoutedScoreAllocationTests(unittest.TestCase):
    def test_select_preserves_critical_pass_and_charges_shared_incumbent_prefix_once(self):
        rows = (Row('0', 'task', True), Row('1', 'task'), Row('2', 'task'))
        matrix = {'start': (True, False, False), 'unsafe': (False, True, True), 'safe': (True, True, False)}
        for posterior in (False, True):
            paid = {('start', '0'): True}

            def evaluate(prompt, row):
                key = (prompt, row.id)
                if key not in paid:
                    paid[key] = matrix[prompt][int(row.id)]
                return Observation(paid[key], {})

            result = select('start', ('unsafe', 'safe'), rows, evaluate, metric_limit=9, posterior=posterior)
            self.assertEqual(result.prompt, 'safe')
            self.assertEqual(result.evaluations, len(paid))
            self.assertLessEqual(result.evaluations, 9)

    def test_select_does_not_start_a_candidate_it_cannot_finish(self):
        rows = tuple(Row(str(index), 'task') for index in range(3))
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(False, {})

        for posterior in (False, True):
            calls.clear()
            result = select('start', ('candidate',), rows, evaluate, metric_limit=5, posterior=posterior)
            self.assertEqual(result.prompt, 'start')
            self.assertEqual(calls, [('start', str(i)) for i in range(3)])
