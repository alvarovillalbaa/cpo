from types import SimpleNamespace
import unittest

from benchmarks.component_merge import attempt_merge, encode
from cpo import Observation
from cpo.composition import merge_components


class ComponentMergeTests(unittest.TestCase):
    def test_merge_combines_independent_changes_and_refuses_conflicts(self):
        base = {'routing': 'old', 'policy': 'old'}
        left = {'routing': 'new', 'policy': 'old'}
        right = {'routing': 'old', 'policy': 'new'}
        self.assertEqual(merge_components(base, left, right), {'routing': 'new', 'policy': 'new'})
        self.assertIsNone(merge_components(base, left, {'routing': 'another', 'policy': 'new'}))
        self.assertIsNone(merge_components(base, base, right))
        self.assertEqual(base, {'routing': 'old', 'policy': 'old'})
        with self.assertRaisesRegex(ValueError, 'same nonempty set'):
            merge_components(base, left, {'policy': 'new'})

    def test_merge_rejects_a_regression_on_either_parents_measured_successes(self):
        ancestor = encode({'a': 'old', 'b': 'old'})
        left = encode({'a': 'new', 'b': 'old'})
        right = encode({'a': 'old', 'b': 'new'})
        result = SimpleNamespace(prompt=left, events=[
            {'kind': 'validated', 'prompt': ancestor, 'passed': []},
            {'kind': 'validated', 'prompt': left, 'parent': ancestor, 'passed': ['left']},
            {'kind': 'validated', 'prompt': right, 'parent': ancestor, 'passed': ['right']},
        ])
        cases = ['left', 'right', 'other']
        for compatible, expected_calls in ((False, cases[:2]), (True, cases)):
            journal = {}

            def evaluate(program, row):
                self.assertEqual(program, {'a': 'new', 'b': 'new'})
                verdict = Observation(compatible or row != 'right', {})
                journal[row] = verdict
                return verdict

            chosen, attempt = attempt_merge(result, cases, evaluate, journal)
            self.assertEqual(list(journal), expected_calls)
            self.assertEqual(attempt['preserved'], compatible)
            self.assertEqual(chosen, attempt['candidate'] if compatible else left)
