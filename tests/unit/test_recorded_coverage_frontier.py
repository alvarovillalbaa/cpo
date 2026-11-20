"""T2 checks for matched-cost and critical-case comparisons."""

import unittest

from benchmarks.recorded_coverage_frontier import affordable, compare, prechecked_cost


class RecordedCoverageFrontierTests(unittest.TestCase):
    def test_strongest_affordable_control_excludes_points_above_budget(self):
        points = {
            'start': {'passes': 6, 'total': 0},
            'more-expensive-tie': {'passes': 9, 'total': 12},
            'cheap-tie': {'passes': 9, 'total': 10},
            'over-budget': {'passes': 10, 'total': 13},
        }
        self.assertEqual(affordable(12, points, points), 'cheap-tie')
        self.assertEqual(affordable(9, points, points), 'start')

    def test_net_gain_cannot_hide_matched_critical_loss(self):
        points = {
            'cpo': {'passes': 3, 'total': 12, 'outcomes': (0b110, 0b001)},
            'gepa': {'passes': 2, 'total': 11, 'outcomes': (0b001, 0b100)},
        }
        result = compare(points, (0b001, 0b010), 'cpo', 'gepa')
        self.assertEqual(result, {'control': 'gepa', 'passDelta': 1, 'lookupSavings': -1,
                                  'matchedCriticalLosses': 1})

    def test_precheck_reuses_baseline_replies_and_only_skips_impossible_search(self):
        record = {'prompt': 'initial', 'nominee': 'candidate', 'qualification': 3, 'search': 11, 'offered': 4}
        self.assertEqual(prechecked_cost(record, 'initial', (True, True)), (0, 2, 0, 1))
        self.assertEqual(prechecked_cost(record, 'initial', (False, True)), (11, 3, 4, 0))
        unchanged = {**record, 'nominee': 'initial', 'qualification': 0}
        self.assertEqual(prechecked_cost(unchanged, 'initial', (True, False)), (11, 2, 4, 0))
        with self.assertRaisesRegex(ValueError, 'cannot be strictly improved'):
            prechecked_cost({**record, 'prompt': 'candidate'}, 'initial', (True, True))
