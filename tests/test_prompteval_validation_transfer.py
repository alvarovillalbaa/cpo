import unittest

from benchmarks.prompteval_validation_transfer import paired, prepare


class ValidationTransferTests(unittest.TestCase):
    def test_transfer_uses_frozen_policy_with_new_subjects(self):
        plan, schedule, source = prepare()
        self.assertEqual(plan['designs']['candidate'], (12, 52))
        self.assertEqual(schedule['validationRows'], 24)
        self.assertEqual(len(source['panels']), 6)
        self.assertTrue(set(plan['subjects']).isdisjoint(plan['tuningSubjects']))
        self.assertEqual(schedule['cycles'] * schedule['qualificationRowsPerCycle'], 32)

    def test_pairing_measures_episode_directions_and_full_cost(self):
        def record(passes, search, qualification):
            return {'holdoutPasses': passes, 'steps': [{'searchLookups': search, 'qualificationLookups': qualification}]}

        left = [record(3, 15, 7), record(2, 10, 6), record(5, 4, 3)]
        right = [record(1, 17, 5), record(4, 13, 5), record(5, 7, 4)]
        result = paired(left, right)
        self.assertEqual(result, {'deltaPasses': 0, 'deltaLookups': -6, 'qualified': True,
                                  'episodes': {'wins': 1, 'ties': 1, 'losses': 1}})
