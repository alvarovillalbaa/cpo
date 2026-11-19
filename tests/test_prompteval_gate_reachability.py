import unittest

from benchmarks.prompteval_gate_reachability import compare_episode, reachable_prompts
from benchmarks.prompteval_single_finalist import METHODS
from benchmarks.prompteval_validation_transfer import CPO


MATRIX = ('1000000000', '0110001010', '0001000000', '1100000011', '0000000000')
FIRST = {'alternatives': ['1', '2', '3'], 'validation': [0, 1], 'qualify': [2, 3]}
SECOND = {'alternatives': ['4'], 'validation': [4, 5], 'qualify': [6, 7]}


class GateReachabilityTests(unittest.TestCase):
    def test_each_relaxation_reaches_only_the_prompts_allowed_at_that_stage(self):
        explored = reachable_prompts(MATRIX, '0', (FIRST, SECOND))
        self.assertEqual(explored['strict-fresh'], [{'0'}, {'0'}, {'0'}])
        self.assertEqual(explored['strict-with-archive'], [{'0'}, {'0'}, {'0', '1'}])
        self.assertEqual(explored['tie-with-archive'][1], {'0', '1'})
        self.assertEqual(explored['qualification-only'][1], {'0', '1', '2'})
        self.assertEqual(explored['any-offered'][-1], {'0', '1', '2', '3', '4'})

    def test_loss_attribution_uses_the_first_bound_that_matches_the_measured_score(self):
        traces = {
            CPO: {'candidate': '0', 'holdoutPasses': 0, 'steps': [{'selected': '0'}]},
            METHODS[1]: {'candidate': '1', 'holdoutPasses': 1},
            METHODS[2]: {'candidate': '3', 'holdoutPasses': 2},
        }
        result = compare_episode(MATRIX, [8, 9], '0', (FIRST,), traces)
        self.assertEqual(result['firstBoundMatchingGepaOnCpoLoss'], {
            METHODS[1]: 'tie-with-archive', METHODS[2]: 'any-offered',
        })

    def test_measured_cpo_must_be_inside_its_liberalized_gate(self):
        traces = {method: {'candidate': '3', 'holdoutPasses': 2, 'steps': [{'selected': '3'}]}
                  for method in METHODS}
        with self.assertRaisesRegex(ValueError, 'outside its optimistic bound'):
            compare_episode(MATRIX, [8, 9], '0', (FIRST,), traces)
