"""Tier 1. Paired resampling contracts using explicit numeric inputs."""

import unittest

from benchmarks.independent_mmlu_cost_uncertainty import deltas, resample


class IndependentMmluCostUncertaintyTests(unittest.TestCase):
    plan = {'cpoPaidLookups': {'cpo': 10}, 'gepaPaidLookups': {'left': 8, 'right': 10, 'too-high': 11},
            'publishedScoreMatchedGepa': {'cpo': 'left'}, 'bootstrapSeed': 1, 'bootstrapDraws': 40}

    def test_reselects_the_better_affordable_control_for_each_draw(self):
        row = {'cpo': 5, 'left': 4, 'right': 6, 'too-high': 10, 'retain-start': 2}
        differences, observed = deltas(row, self.plan)
        self.assertEqual(observed, {'cpo': 'right'})
        self.assertEqual(differences, {'cpo/affordable': -1, 'cpo/score-matched': 1, 'cpo/retain-start': 3})

    def test_shared_resample_keeps_identical_case_vectors_tied(self):
        rows = [{name: v for name in ('cpo', 'left', 'right', 'too-high', 'retain-start')} for v in (0, 1, 8)]
        draw, options = resample({'first': rows, 'second': rows}, self.plan)
        self.assertTrue(all(gaps == [0] * 40 for gaps in draw.values()))
        self.assertEqual(options['cpo'], {'left': 40})

    def test_resample_can_select_either_control(self):
        rows = [dict(cpo=2, left=3, right=0, **{'too-high': 8, 'retain-start': 1}),
                dict(cpo=2, left=0, right=3, **{'too-high': 8, 'retain-start': 1})]
        _, options = resample({'first': rows}, self.plan)
        self.assertEqual(set(options['cpo']), {'left', 'right'})
