from unittest import TestCase

from benchmarks.reserved_regression_guard import guard, reserve_cases


class ReservedRegressionGuardTests(TestCase):
    def choice(self, final='1010', *, require_upgrade=False, budget=8):
        outcomes = {'start': '1100', 'final': final}
        looked_up = set()

        def evaluate(prompt, case):
            key = (prompt, case)
            self.assertNotIn(key, looked_up)
            looked_up.add(key)
            return outcomes[prompt][case] == '1'

        chosen, reads, status = guard('start', 'final', range(4), evaluate, remaining=budget, seed=1,
                                      require_upgrade=require_upgrade)
        self.assertEqual(len(reads), len(looked_up))
        return chosen, status

    def test_ties_remain_deployed_unless_upgrade_is_required(self):
        self.assertEqual(self.choice(), ('final', 'checked'))
        self.assertEqual(self.choice(require_upgrade=True), ('start', 'checked'))

    def test_return_to_start_on_a_strict_loss(self):
        self.assertEqual(self.choice('1000'), ('start', 'checked'))
        self.assertEqual(self.choice('1110'), ('final', 'checked'))

    def test_budget_admits_a_complete_guard_or_skips(self):
        self.assertEqual(self.choice('1000', budget=7), ('final', 'insufficient-budget'))

    def test_reserve_excludes_every_scheduled_role(self):
        layouts = [{'train': [0, 1], 'validation': [2, 3], 'qualify': [4, 5]},
                   {'train': [5, 6], 'validation': [7, 8], 'qualify': [9, 10]}]
        reserve = reserve_cases(24, [11, 12], layouts, 43)
        self.assertEqual(len(reserve), 8)
        self.assertEqual(len(set(reserve)), 8)
        self.assertTrue(set(reserve).isdisjoint(range(13)))
        self.assertEqual(reserve_cases(24, [11, 12], layouts, 43), reserve)
