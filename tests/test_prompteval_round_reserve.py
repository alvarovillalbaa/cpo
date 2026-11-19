import unittest
from unittest.mock import patch

from benchmarks.prompteval_round_reserve import attributed_step
from cpo import Observation, Row, cycle


class RoundReserveTests(unittest.TestCase):
    def test_counts_unique_lookups_by_role_and_uses_the_built_in_reserve(self):
        layout = {'train': [2], 'validation': [0, 1], 'qualify': [3]}
        seen = []

        def search(initial, train, validation, evaluate, propose, *, adaptive):
            seen.append(adaptive)
            for row in (train[0], validation[0], validation[0], validation[1]):
                evaluate(initial, row)
            for row in validation:
                evaluate('complete', row)
            evaluate('partial', validation[0])

        def upstream(_method, _matrix, incumbent, _layout, _plan):
            cycle.search(incumbent, [Row('2', 'task')], [Row('0', 'task'), Row('1', 'task')],
                         lambda *_: Observation(True, {}), None, adaptive=True)
            return {'searchLookups': 6}

        with patch.object(cycle, 'search', search):
            for fixed_round in (False, True):
                result = attributed_step(upstream, 'cpo-cycle', [], 'old', layout, {}, fixed_round=fixed_round)
                self.assertEqual(result['searchByRole'], {'train': 1, 'validation': 5})
                self.assertEqual(result['validationByCandidate'],
                                 {'incumbent': 2, 'completeChallenger': 2, 'partialChallenger': 1})
        self.assertEqual(seen, [True, False])

    def test_missing_observations_fail_reconciliation(self):
        layout = {'train': [2], 'validation': [0, 1]}
        with self.assertRaisesRegex(ValueError, 'reconcile by role'):
            attributed_step(lambda *_: {'searchLookups': 1}, 'cpo-cycle', [], 'old', layout, {}, fixed_round=False)
