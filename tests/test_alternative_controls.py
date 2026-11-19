from importlib.metadata import PackageNotFoundError, version
import json
import unittest

from benchmarks import alternative_controls as controls, grounded, typed_policy
from cpo import Observation


try:
    GEPA_VERSION = version('gepa')
except PackageNotFoundError:
    GEPA_VERSION = None


class AlternativeControlsTests(unittest.TestCase):
    def test_demonstration_transfers_only_to_a_matching_topic(self):
        ticket = typed_policy.cohorts()['ticket']
        first, second = ticket['train'][:2]
        matching = next(row for row in ticket['holdout'] if row['input'].split('.')[0] == first['input'].split('.')[0])
        other = next(row for row in ticket['holdout'] if row['input'].split('.')[0] == second['input'].split('.')[0])
        program = controls.encode(grounded.BASELINE, [0])
        self.assertEqual(json.loads(controls.complete('ticket', program, matching['input'], ticket['train'])),
                         matching['expected'])
        self.assertEqual(json.loads(controls.complete('ticket', program, other['input'], ticket['train'])),
                         {'queue': 'GENERAL'})

    def test_history_compares_full_scores_in_ascending_order(self):
        initial, repair, rewrite, new = map(controls.encode, ('initial', 'repair', 'rewrite', 'new'))
        counts = {initial: (0, 0), repair: (1, 1), rewrite: (1, 2), new: (2, 2)}

        def evaluate(prompt, row):
            exact, fields = counts[prompt]
            return Observation(row < exact, {}, int(row < fields))

        def reflect(parent, history):
            self.assertEqual(parent, rewrite)
            self.assertEqual(history, [
                {'instruction': 'initial', 'exact': 0, 'fields': 0},
                {'instruction': 'repair', 'exact': 1, 'fields': 1},
                {'instruction': 'rewrite', 'exact': 1, 'fields': 2},
            ])
            return new

        self.assertEqual(controls.scored_history(initial, (initial, rewrite, repair), [0, 1],
                                                evaluate, reflect, 8), new)

    @unittest.skipUnless(GEPA_VERSION == '0.1.4', 'requires pinned GEPA benchmark dependency')
    def test_matched_report_preserves_controls_and_caps(self):
        result = controls.report()
        primary = result['budgets']['56']
        scores = primary['totals']
        self.assertEqual(scores['cpo-joint'], {'exact': 162, 'searchCalls': 288})
        self.assertEqual(scores['gepa-joint'], {'exact': 162, 'searchCalls': 298})
        self.assertFalse(primary['comparisons']['gepa-joint']['qualified'])
        self.assertFalse(primary['qualified'])
        for cap, scored in result['budgets'].items():
            for trial in scored['trials']:
                self.assertEqual(set(trial['arms']), set(controls.ARMS))
                self.assertTrue(all('-train-' in row for row in trial['trainingDemoIDs']))
                for evaluation in trial['arms'].values():
                    self.assertLessEqual(evaluation['evaluations'], int(cap))
                    self.assertLessEqual(evaluation['reflections'], controls.REFLECTION_LIMIT)
                    self.assertTrue(all('-holdout-' in row for row in evaluation['holdout']))


if __name__ == '__main__':
    unittest.main()
