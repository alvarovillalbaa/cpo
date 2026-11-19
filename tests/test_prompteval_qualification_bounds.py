import unittest

from benchmarks.prompteval_qualification_bounds import qualification_cost


class QualificationReplayTests(unittest.TestCase):
    def test_an_odd_prefix_does_not_recharge_preflight_observations(self):
        step = {'incumbent': 'old', 'challenger': 'new', 'archiveNominee': 'archive', 'archivePromoted': False,
                'selected': 'old', 'qualificationLookups': 3,
                'qualification': [('old', 1, True), ('archive', 1, False), ('new', 1, False)]}
        self.assertEqual(qualification_cost(step, {'seed': 0, 'qualify': [1]}), (2, 3))

    def test_full_decision_must_match_the_certificate(self):
        step = {'incumbent': 'old', 'challenger': 'new', 'archiveNominee': None, 'archivePromoted': False,
                'selected': 'new', 'qualificationLookups': 2,
                'qualification': [('old', 1, True), ('new', 1, False)]}
        with self.assertRaisesRegex(ValueError, 'differs from the full qualification'):
            qualification_cost(step, {'seed': 0, 'qualify': [1]})
