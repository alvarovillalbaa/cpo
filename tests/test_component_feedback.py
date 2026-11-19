import unittest

from benchmarks.component_feedback import next_edit, rank_edits
from benchmarks.component_merge import encode
from cpo import Observation


class ComponentFeedbackTests(unittest.TestCase):
    def test_archive_reuses_only_local_evidence_from_paid_training(self):
        parent = {'aggregate': 'broad', 'precedence': 'off', 'eligibility': 'off'}
        cousin = {**parent, 'eligibility': 'guarded'}
        stale = {**cousin, 'aggregate': 'guarded'}
        journal = {
            (encode(cousin), 'paid'): Observation(False, {'diagnosis': 'regression:aggregate'}),
            (encode(stale), 'other'): Observation(False, {'diagnosis': 'regression:aggregate'}),
            (encode(cousin), 'interaction'): Observation(False, {'diagnosis': 'The combined repairs conflict on this legacy case'}),
            (encode(cousin), 'validation'): Observation(False, {'diagnosis': 'missing:eligibility'}),
        }
        training = {case: {'critical': True} for case in ('paid', 'other', 'interaction')}
        self.assertEqual(rank_edits(parent, journal, training, archive=False), [])
        self.assertEqual(rank_edits(parent, journal, training, archive=True), [('aggregate', 'guarded', 2)])

    def test_same_parent_conflict_yields_distinct_rollbacks(self):
        parent = {'aggregate': 'guarded', 'precedence': 'guarded', 'eligibility': 'off'}
        journal = {(encode(parent), 'train'): Observation(
            False, {'diagnosis': 'The combined repairs conflict on this legacy case'})}
        training = {'train': {'critical': True}}
        seen = set()
        self.assertEqual(next_edit(parent, journal, training, seen, archive=True)['aggregate'], 'off')
        self.assertEqual(next_edit(parent, journal, training, seen, archive=True)['precedence'], 'off')
        self.assertIs(next_edit(parent, journal, training, seen, archive=True), parent)

    def test_repeated_case_diagnostics_count_once_per_action(self):
        parent = {'aggregate': 'off', 'precedence': 'off', 'eligibility': 'off'}
        observed = Observation(False, {'diagnosis': 'missing:aggregate'})
        journal = {(encode(parent), 'same'): observed,
                   (encode({**parent, 'eligibility': 'guarded'}), 'same'): observed}
        for case in ('first', 'second'):
            journal[encode(parent), case] = Observation(False, {'diagnosis': 'missing:precedence'})
        training = {case: {'critical': False} for case in ('same', 'first', 'second')}
        self.assertEqual(rank_edits(parent, journal, training, archive=True)[0], ('precedence', 'guarded', 0))
