from itertools import product
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

    def test_shortlist_only_certifies_the_highest_screened_challenger(self):
        rows = [Row(str(i), 'task') for i in range(6)]
        evaluate = self.evaluate({'base': {'2'}, 'later': {'2', '3', '4', '5'}, 'first': {'0', '1'}})
        result = select_pool(['base', 'later', 'first'], rows, evaluate,
                             metric_limit=18, screen_rows=2, max_challenges=1)
        self.assertEqual(result.prompt, 'first')
        self.assertEqual([row for prompt, row in self.calls if prompt == 'later'], ['0', '1'])

    def test_adaptive_rejection_uses_cached_failure_before_buying_validation(self):
        rows = [Row('screen', 'task'), Row('protected', 'task', critical=True), Row('other', 'task')]
        scores = {'base': {'protected', 'other'}, 'challenger': {'protected', 'other'}}
        baseline = select_pool(scores, rows, self.evaluate(scores), metric_limit=6, screen_rows=1)
        adaptive = select_pool(scores, rows, self.evaluate(scores), metric_limit=6, screen_rows=1,
                               adaptive_rejection=True)
        self.assertEqual((baseline.prompt, baseline.evaluations), ('base', 5))
        self.assertEqual((adaptive.prompt, adaptive.evaluations), ('base', 4))
        self.assertEqual(self.calls[-1], ('challenger', 'screen'))

    def test_adaptive_rejection_skips_a_challenge_it_cannot_finish(self):
        rows = [Row(str(index), 'task') for index in range(4)]
        scores = {'base': {'0', '1'}, 'new': {'0', '1', '2', '3'}}
        adaptive = select_pool(scores, rows, self.evaluate(scores), metric_limit=7, adaptive_rejection=True)
        self.assertEqual((adaptive.prompt, adaptive.evaluations), ('base', 4))
        self.assertTrue(all(prompt == 'base' for prompt, _row in self.calls))

    def test_adaptive_rejection_preserves_exact_funded_results_and_critical_passes(self):
        rows = [Row(str(index), 'task', critical=index == 1) for index in range(3)]
        prompts = ['base', 'a', 'b']
        for outcomes in product((False, True), repeat=9):
            scores = {prompt: {row.id for row, passed in zip(rows, outcomes[index * 3:index * 3 + 3]) if passed}
                      for index, prompt in enumerate(prompts)}
            for screen in (0, 1, 2):
                baseline = select_pool(prompts, rows, self.evaluate(scores), metric_limit=9, screen_rows=screen)
                adaptive = select_pool(prompts, rows, self.evaluate(scores), metric_limit=9, screen_rows=screen,
                                       adaptive_rejection=True)
                self.assertEqual((baseline.prompt, baseline.validation_passes),
                                 (adaptive.prompt, adaptive.validation_passes))
                self.assertEqual(len(self.calls), len(set(self.calls)))
                self.assertEqual({row for prompt, row in self.calls if prompt == adaptive.prompt},
                                 {row.id for row in rows})
                if '1' in scores['base']:
                    self.assertIn('1', scores[adaptive.prompt])


if __name__ == '__main__':
    unittest.main()
