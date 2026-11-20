from collections import Counter
from unittest import TestCase

from benchmarks.proposal_short_validation import archive_episode, short_search


class ShortProposalValidationTests(TestCase):
    def setUp(self):
        self.layout = {'alternatives': ['1', '2'], 'train': [6], 'validation': [0, 1, 2, 3],
                       'qualify': [4, 5], 'seed': 19}
        self.plan = {'evaluationLookupLimit': 8, 'probeSize': 1, 'minimumQualificationGain': 1}

    def replay(self, matrix):
        selected, calls, traces = archive_episode(matrix, '0', [self.layout], self.plan, width=2)
        self.assertEqual(calls['screenLookups'], 4)
        self.assertEqual(calls['completionLookups'], 4)
        self.assertEqual(calls['searchLookups'], 8)
        self.assertEqual(calls['screenNominees'], 1)
        return selected, calls, traces[0][-1]

    def test_short_panel_win_without_full_gain_never_enters_qualification(self):
        selected, counts, qualification = self.replay(['0011000', '1100110', '0000000'])
        self.assertEqual(selected, 0)
        self.assertEqual(counts['fullPanelRejections'], 1)
        self.assertEqual(counts['expected'], 0)
        self.assertEqual(qualification, [])

    def test_full_win_still_needs_the_untouched_qualification_panel(self):
        selected, counts, qualification = self.replay(['0011000', '1101110', '0000000'])
        self.assertEqual(selected, 1)
        self.assertEqual(counts['fullPanelRejections'], 0)
        self.assertEqual({reply[0] for reply in qualification}, {'0', '1'})
        self.assertTrue({reply[1] for reply in qualification}.issubset({'4', '5'}))
        rejected, _, qualification = self.replay(['0011000', '1101000', '0000000'])
        self.assertEqual(rejected, 0)
        self.assertTrue(qualification)

    def test_incomplete_pair_funding_cannot_dispatch(self):
        search = short_search(2, Counter())
        with self.assertRaisesRegex(ValueError, 'enough lookups'):
            search('0', (), (None,) * 4, self.fail, self.fail, metric_limit=7)
