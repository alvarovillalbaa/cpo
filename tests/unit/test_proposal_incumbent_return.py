from unittest import TestCase

from benchmarks.proposal_incumbent_return import archive_episode


class ProposalIncumbentReturnTests(TestCase):
    def setUp(self):
        self.plan = {'evaluationLookupLimit': 12, 'probeSize': 1, 'minimumQualificationGain': 1}
        self.layouts = [
            {'alternatives': [str(2 * cycle + 1), str(2 * cycle + 2)],
             'train': [offset], 'validation': [offset + 1, offset + 2],
             'qualify': [offset + 3, offset + 4], 'seed': cycle}
            for cycle, offset in enumerate((0, 5, 10))
        ]
        self.matrix = ['000000111100000', '011110000001111'] + ['0' * 15] * 5

    def test_previous_prompt_can_return_only_with_fresh_qualification(self):
        final, counts, history = archive_episode(self.matrix, '0', self.layouts[:2], self.plan, policy='return')
        self.assertEqual(final, 0)
        self.assertEqual(counts['reservedSlots'], 1)
        self.assertEqual(counts['returnPromoted'], 1)
        self.assertEqual(history[-1][:4], ('1', '0', '0', '0'))
        self.assertEqual({r[0] for r in history[-1][-1]}, {'0', '1'})
        self.assertTrue({r[1] for r in history[-1][-1]}.issubset({'8', '9'}))
        self.assertEqual(self.layouts[1]['alternatives'], ['3', '4'])

    def test_failed_return_expires_at_the_end_of_its_cycle(self):
        self.matrix[0] = '000000110000000'
        final, counts, history = archive_episode(self.matrix, '0', self.layouts, self.plan, policy='return')
        self.assertEqual(final, 1)
        self.assertEqual(counts['returnNominated'], 1)
        self.assertEqual(counts['returnPromoted'], 0)
        self.assertEqual(counts['reservedSlots'], 1)
        self.assertIsNone(history[-1][1])

    def test_vacant_control_removes_the_slot_without_opening_a_return(self):
        final, counts, history = archive_episode(self.matrix, '0', self.layouts[:2], self.plan, policy='vacant')
        self.assertEqual(final, 1)
        self.assertEqual(counts['reservedSlots'], 1)
        self.assertEqual(counts['returnOpened'], 0)
        self.assertEqual(history[-1][-1], [])
