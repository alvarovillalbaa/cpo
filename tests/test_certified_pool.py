from itertools import product
import unittest

from cpo import Observation, Row, select_certified_pool


class CertifiedPoolTests(unittest.TestCase):
    def test_returns_a_sound_partial_certificate(self):
        rows = [Row(str(i), 'task', critical=i == 4) for i in range(5)]
        passes = {'incumbent': {'4'}, 'challenger': {'0', '2', '4'}}
        seen = []

        def evaluate(prompt, row):
            seen.append((prompt, row.id))
            return Observation(row.id in passes[prompt], {})

        result = select_certified_pool(passes, rows, evaluate, metric_limit=7)
        self.assertEqual(result.prompt, 'challenger')
        self.assertEqual((result.lower_pass_bound, result.upper_pass_bound), (2, 5))
        self.assertEqual(seen[-2:], [('challenger', '4'), ('challenger', '0')])
        self.assertEqual(result.evaluations, 7)

    def test_a_perfect_incumbent_needs_no_challenger_calls(self):
        rows = [Row('only', 'task', critical=True)]

        def evaluate(prompt, _row):
            self.assertEqual(prompt, 'incumbent')
            return Observation(True, {})

        result = select_certified_pool(['incumbent', 'challenger'], rows, evaluate, metric_limit=10)
        self.assertEqual((result.prompt, result.evaluations), ('incumbent', 1))

    def test_every_small_matrix_preserves_bounds_budget_and_critical_rows(self):
        prompts = ('base', 'a', 'b')
        rows = [Row(str(i), 'task', critical=i != 1) for i in range(3)]
        for bits in product((False, True), repeat=9):
            table = {(prompt, row.id): value for (prompt, row), value in zip(product(prompts, rows), bits)}
            incumbent_passes = sum(table['base', row.id] for row in rows)
            for budget in range(3, 10):
                calls = []

                def evaluate(prompt, row):
                    calls.append((prompt, row.id))
                    return Observation(table[prompt, row.id], {})

                result = select_certified_pool(prompts, rows, evaluate, metric_limit=budget)
                self.assertEqual(len(calls), len(set(calls)))
                self.assertEqual(result.evaluations, len(calls))
                self.assertLessEqual(result.evaluations, budget)
                actual = sum(table[result.prompt, row.id] for row in rows)
                self.assertLessEqual(result.lower_pass_bound, actual)
                self.assertLessEqual(actual, result.upper_pass_bound)
                if result.prompt != 'base':
                    self.assertGreater(result.lower_pass_bound, incumbent_passes)
                    for row in rows:
                        if row.critical and table['base', row.id]:
                            self.assertIn((result.prompt, row.id), calls)
                            self.assertTrue(table[result.prompt, row.id])


if __name__ == '__main__':
    unittest.main()
