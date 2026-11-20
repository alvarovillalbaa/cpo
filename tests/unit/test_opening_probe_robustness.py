from unittest import TestCase

from benchmarks.opening_probe_robustness import deduplicate_features, feature_map, rank_coverage
from cpo import Row
from cpo.routed_repair_cycle import _rank_probes


class OpeningProbeRobustnessTests(TestCase):
    def test_recoded_columns_share_one_vote_and_keep_distinct_missingness(self):
        raw = {'first': {'kind': 'new', 'alias': 7, 'partial': True},
               'second': {'kind': 'old', 'alias': 8},
               'third': {'kind': 'new', 'alias': 7, 'partial': False}}
        expected = {'first': {'kind': 'new', 'partial': True}, 'second': {'kind': 'old'},
                    'third': {'kind': 'new', 'partial': False}}
        self.assertEqual(deduplicate_features(raw), expected)
        self.assertEqual(raw['first']['alias'], 7)

    def test_coverage_prefers_the_remaining_positive_signal(self):
        train = [Row(name, 'family') for name in ('a', 'copy', 'b')]
        validation = [Row(name, 'family') for name in ('miss-one', 'miss-two', 'pass')]
        signals = {'a': ('left',), 'copy': ('left',), 'b': ('right',),
                   'miss-one': ('left', 'right'), 'miss-two': ('left',), 'pass': ('other',)}

        def extract(row):
            return signals[row.id]

        own = (False, False, True)
        self.assertEqual(_rank_probes(train, validation, own, extract), train)
        self.assertEqual(rank_coverage(train, validation, own, extract), [train[0], train[2], train[1]])

    def test_feature_modes_use_only_train_and_validation_inputs(self):
        row = {'id': 'same', 'input': 'Zone=1; Priority=2; Reason=0; Channel=2.'}
        rows = {'train': [row], 'validation': [], 'holdout': [{'id': 'inaccessible'}]}
        self.assertEqual(tuple(feature_map('dispatch', rows, 'clean')['same']),
                         ('Zone', 'Priority', 'Reason', 'Channel'))
        self.assertEqual(tuple(feature_map('dispatch', rows, 'missing-field')['same']),
                         ('Zone', 'Priority', 'Reason'))
        redundant = feature_map('dispatch', rows, 'redundant-metadata')['same']
        self.assertEqual(len({value for key, value in redundant.items() if key.startswith('export_bucket_')}), 1)
