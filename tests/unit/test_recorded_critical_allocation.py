"""T2 panel allocation tests using declared case categories."""

import unittest

from benchmarks.recorded_critical_allocation import allocate


class CriticalAllocationTests(unittest.TestCase):
    def test_moves_training_coverage_without_using_held_rows_or_changing_quotas(self):
        layout = (('rare', 'ordinary-train'), ('common-val', 'ordinary-val'), ('common-qual',))
        risk = {'rare': 'a', 'common-val': 'b', 'common-qual': 'b', 'held': 'c'}
        allocated = allocate(layout, risk, 42)
        self.assertEqual(allocated, allocate(layout, risk, 42))
        for panels in allocated.values():
            rows = [row for panel in panels for row in panel]
            self.assertCountEqual(rows, [row for panel in layout for row in panel])
            self.assertEqual(tuple(map(len, panels)), (2, 2, 1))
            self.assertEqual(tuple(len(set(panel) & risk.keys()) for panel in panels), (1, 1, 1))

        risk_layout = allocated['risk-coverage']
        self.assertEqual({risk[row] for panel in risk_layout[1:] for row in panel if row in risk}, {'a', 'b'})

        def moved(panels):
            return sum(len(set(before) - set(after)) for before, after in zip(layout, panels, strict=True))

        self.assertEqual(moved(risk_layout), 2)
        self.assertEqual(moved(risk_layout), moved(allocated['matched-moves']))

    def test_keeps_existing_order_if_coverage_is_already_optimal(self):
        layout = (('z', 't'), ('b', 'a'), ('q',))
        result = allocate(layout, {'z': 'same', 'b': 'same', 'q': 'different'}, 7)
        self.assertEqual(result, dict.fromkeys(result, layout))

    def test_rejects_overlapping_role_inputs(self):
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            allocate((('row',), ('row',), ('other',)), {'row': 'x'}, 42)
