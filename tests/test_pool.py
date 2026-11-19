import unittest

from cpo import Observation, Row, select_pool


class PoolTests(unittest.TestCase):
    def evaluate(self, scores):
        def observe(prompt, row):
            self.calls.append((prompt, row.id))
            return Observation(row.id in scores[prompt], {})
        self.calls = []
        return observe

    def test_partial_high_score_cannot_replace_the_incumbent(self):
        rows = [Row(str(i), 'task') for i in range(4)]
        evaluate = self.evaluate({'base': {'0'}, 'new': {'1', '2', '3'}})
        result = select_pool(['base', 'new'], rows, evaluate, metric_limit=6)
        self.assertEqual(result.prompt, 'base')
        self.assertEqual(result.evaluations, 6)
        self.assertEqual(len(self.calls), len(set(self.calls)))

    def test_screen_reuses_calls_and_fully_validates_candidate(self):
        rows = [Row(str(i), 'task') for i in range(6)]
        evaluate = self.evaluate({'base': {'0'}, 'weak': {'2'}, 'strong': {'0', '1', '4', '5'}})
        result = select_pool(['base', 'weak', 'strong'], rows, evaluate, metric_limit=14, screen_rows=2)
        self.assertEqual(result.prompt, 'strong')
        self.assertEqual(result.validation_passes, 4)
        self.assertEqual({row for prompt, row in self.calls if prompt == 'strong'}, {row.id for row in rows})
        self.assertEqual(len(self.calls), len(set(self.calls)))

    def test_critical_pass_is_preserved_even_if_total_drops_later(self):
        rows = [Row('protected', 'task', critical=True), *(Row(str(i), 'task') for i in range(4))]
        evaluate = self.evaluate({'base': {'protected'}, 'higher': {'0', '1', '2', '3'}})
        result = select_pool(['base', 'higher'], rows, evaluate, metric_limit=10)
        self.assertEqual(result.prompt, 'base')
        self.assertEqual(self.calls[-1], ('higher', 'protected'))

    def test_impossible_screen_rejected_before_evaluation(self):
        rows = [Row(str(i), 'task') for i in range(6)]
        with self.assertRaisesRegex(ValueError, 'complete first challenge'):
            select_pool(['base', 'a', 'b'], rows, lambda *_: self.fail('unexpected lookup'),
                        metric_limit=13, screen_rows=2)


if __name__ == '__main__':
    unittest.main()
