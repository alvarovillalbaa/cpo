import unittest

from benchmarks.routed_training_corroboration import reserve_panel


class RoutedTrainingCorroborationTests(unittest.TestCase):
    def test_panel_excludes_every_cycles_validation_and_qualification(self):
        layouts = (
            {'train': [3, 4, 6, 7], 'validation': [0, 1], 'qualify': [2]},
            {'train': [0, 8, 11], 'validation': [3, 4], 'qualify': [5]},
        )
        panel = reserve_panel(14, [10, 11, 12], layouts, 17)
        self.assertEqual(panel, reserve_panel(14, [10, 11, 12], layouts, 17))
        self.assertEqual(set(panel), {6, 7, 8, 9, 13})
        self.assertEqual(set(panel[:3]), {6, 7, 8})

    def test_panel_requires_five_distinct_eligible_cases(self):
        layout = {'train': [3, 4, 5], 'validation': [1], 'qualify': [2]}
        with self.assertRaisesRegex(ValueError, 'disjoint five-case'):
            reserve_panel(6, [0], [layout], 0)
