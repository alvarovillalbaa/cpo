import unittest

from benchmarks.bounded_transfer_matched_cost import episode_cost
from cpo._contract import digest


class BoundedTransferMatchedCostTests(unittest.TestCase):
    def make_step(self, outcome):
        return {
            'incumbent': 'old', 'challenger': 'old', 'selected': 'old',
            'archivePromoted': False, 'archiveNominee': None,
            'searchLookups': 1, 'searchSha256': digest([('old', 0, outcome)]),
            'qualificationLookups': 0, 'qualification': [],
        }

    def test_search_reuse_is_local_to_one_episode(self):
        layout = {'train': [], 'validation': [0], 'alternatives': ['new'], 'qualify': [], 'seed': 3}
        trace = {'steps': [self.make_step(True)] * 2, 'holdoutPasses': 2, 'evaluations': 2}
        calls = [{('old', 0): True}] * 2
        for _ in range(2):
            cost = episode_cost(trace, [layout] * 2, calls)
            self.assertEqual(cost['searchLookups'], 2)
            self.assertEqual(cost['searchAfterReuse'], 1)

    def test_cache_refuses_conflicting_replies_even_if_each_cycle_digest_matches(self):
        layout = {'train': [], 'validation': [0], 'alternatives': ['new'], 'qualify': [], 'seed': 3}
        trace = {'steps': [self.make_step(True), self.make_step(False)], 'holdoutPasses': 2, 'evaluations': 2}
        with self.assertRaisesRegex(ValueError, 'one exact outcome'):
            episode_cost(trace, [layout] * 2, [{('old', 0): True}, {('old', 0): False}])

    def test_sufficient_qualification_prefix_preserves_promotion(self):
        layout = {'train': [], 'validation': [0], 'alternatives': ['new'], 'qualify': [1, 2], 'seed': 3}
        replies = [('old', case, False) for case in (1, 2)] + [('new', case, True) for case in (1, 2)]
        step = {**self.make_step(True), 'challenger': 'new', 'selected': 'new',
                'qualificationLookups': 4, 'qualification': replies}
        trace = {'steps': [step], 'holdoutPasses': 2, 'evaluations': 5}
        cost = episode_cost(trace, [layout], [{('old', 0): True}])
        self.assertEqual(cost['fullQualification'], 4)
        self.assertEqual(cost['qualificationAfterStop'], 3)
