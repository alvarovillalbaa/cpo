import unittest

from benchmarks.archive_complementarity_transfer import nominate_complement


class ArchiveComplementarityTests(unittest.TestCase):
    history = [
        {'incumbent': 'complement', 'challenger': 'old', 'selected': 'old'},
        {'incumbent': 'old', 'challenger': 'recent', 'selected': 'old'},
    ]

    def test_observed_complementary_gain_outweighs_recency(self):
        evidence = {'old': {1: False, 2: True}, 'complement': {1: True}, 'recent': {2: True}}
        result = nominate_complement('old', self.history, set(), evidence, require_win=False)
        self.assertEqual(result, 'complement')

    def test_unpaired_replies_do_not_count_as_wins_and_missing_evidence_can_keep_recency(self):
        evidence = {'old': {1: False}, 'complement': {2: True}}
        self.assertEqual(nominate_complement('old', self.history, set(), evidence, require_win=False), 'recent')
        self.assertIsNone(nominate_complement('old', self.history, set(), evidence, require_win=True))

    def test_an_attempted_pair_is_ineligible_even_when_it_has_a_known_win(self):
        evidence = {'old': {1: False}, 'complement': {1: True}}
        result = nominate_complement('old', self.history, {('old', 'complement')}, evidence, require_win=True)
        self.assertIsNone(result)
