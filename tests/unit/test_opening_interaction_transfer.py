import json
from unittest import TestCase

from benchmarks import opening_interaction_transfer as interactions


class OpeningInteractionTransferTests(TestCase):
    def setUp(self):
        self.task = 'venue'
        self.groups = interactions.panel(self.task, 'three-exceptions', interactions.SEEDS[0])

    def test_splits_are_pairwise_disjoint_and_cover_each_conjunction(self):
        seen = set()
        for cohort in self.groups.values():
            rows = {row['input'] for row in cohort}
            self.assertTrue(rows.isdisjoint(seen))
            seen.update(rows)
            for keys in zip(*(interactions.conjunctions(self.task, row['input']) for row in cohort), strict=True):
                self.assertEqual(len(set(keys)), 9)

    def test_three_overlapping_misses_need_three_distinct_witnessed_repairs(self):
        training = self.groups['train']
        fields = interactions.TASKS[self.task][1]
        opening = json.loads(interactions.opening('three-exceptions', {
            'task': self.task, 'input': {'labeledTraining': training}}))['rewrite']
        current = opening
        for index in range(3):
            feedback = [
                {'id': row['id'], 'observed': interactions.complete(
                    self.task, interactions.typed.programs.encode(current), row['input'], training)}
                for row in training
            ]
            updated = json.loads(interactions.repair({
                'task': self.task, 'input': {'labeledTraining': training, 'current': current,
                                             'recentFeedback': feedback}}))['instruction']
            old, new = json.loads(current), json.loads(updated)
            self.assertEqual(sum(old[field][key] != new[field][key]
                                 for field in fields for key in old[field]), 1)
            current = updated
        self.assertEqual(json.loads(current), interactions.learned_rules(self.task, training))

    def test_pair_features_have_no_qualification_or_holdout_access(self):
        solo = interactions.feature_map(self.task, self.groups, False)
        combined = interactions.feature_map(self.task, self.groups, True)
        self.assertEqual(set(solo), set(combined))
        self.assertEqual(len(combined), 39)
        for row_id, features in combined.items():
            self.assertEqual(len(features), 10)
            self.assertTrue(solo[row_id].items() <= features.items())
