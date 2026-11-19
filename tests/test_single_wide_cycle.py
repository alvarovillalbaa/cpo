import unittest

from benchmarks.single_wide_cycle import allow_widening


class SingleWideCycleTests(unittest.TestCase):
    def allowed(self, method, index, *, incumbent='start', spent=44, used=False):
        return allow_widening(method, index, 4, incumbent=incumbent, start='start',
                              spent=spent, limit=52, used=used)

    def test_fixed_screens_keep_calendar_positions(self):
        self.assertEqual([i for i in range(1, 5) if self.allowed('wide-first', i)], [1])
        self.assertEqual([i for i in range(1, 5) if self.allowed('wide-final', i)], [4])

    def test_late_start_uses_the_actual_incumbent_and_only_widens_once(self):
        self.assertFalse(self.allowed('late-at-start', 2))
        self.assertFalse(self.allowed('late-at-start', 3, incumbent='promoted'))
        self.assertTrue(self.allowed('late-at-start', 3))
        self.assertFalse(self.allowed('late-at-start', 4, used=True))

    def test_credit_uses_the_worst_case_remaining_search_charge(self):
        self.assertFalse(self.allowed('final-with-credit', 3, spent=0))
        self.assertTrue(self.allowed('final-with-credit', 4, spent=44))
        self.assertFalse(self.allowed('final-with-credit', 4, spent=45))
