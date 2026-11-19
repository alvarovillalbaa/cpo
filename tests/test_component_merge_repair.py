import unittest

from benchmarks.component_merge_repair import repair_from_training
from cpo import Observation


class MergeRepairTests(unittest.TestCase):
    def test_only_observed_component_regressions_are_repaired(self):
        program = {'aggregate': 'broad', 'precedence': 'broad', 'eligibility': 'off'}
        observations = {'train-a': 'regression:aggregate missing:eligibility', 'train-b': ''}
        seen = []

        def observe(candidate, case):
            self.assertEqual(candidate, program)
            seen.append(case)
            return Observation(not observations[case], {'diagnosis': observations[case]})

        probes = ['train-a', 'train-b']
        self.assertEqual(repair_from_training(program, probes, observe, repair=True),
                         {'aggregate': 'guarded', 'precedence': 'broad', 'eligibility': 'off'})
        self.assertEqual(seen, probes)
        self.assertIsNone(repair_from_training(program, probes, observe, repair=False))
        self.assertEqual(program['aggregate'], 'broad')

    def test_interaction_has_no_local_repair(self):
        verdict = Observation(False, {'diagnosis': 'The combined repairs conflict on this legacy case'})
        self.assertIsNone(repair_from_training({'aggregate': 'broad'}, ['train'], lambda *_: verdict, repair=True))
