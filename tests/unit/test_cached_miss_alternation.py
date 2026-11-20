from collections import Counter
from unittest import TestCase

from benchmarks.cached_miss_alternation import select
from cpo import Observation, Row
from cpo.lazy_incumbent import select_with_lazy_incumbent


class CachedMissAlternationTests(TestCase):
    matrix = {'incumbent': '01001', 'first': '00000', 'second': '01011'}

    def screen(self, history, *, baseline=False):
        observations, stats = [], Counter()
        rows = [Row(str(i), 'task') for i in range(5)]

        def measure(prompt, row):
            key = (prompt, row.id)
            self.assertNotIn(key, observations)
            observations.append(key)
            return Observation(self.matrix[prompt][int(row.id)] == '1', {})

        args = ('incumbent', ('first', 'second'), rows, measure)
        if baseline:
            result = select_with_lazy_incumbent(*args, metric_limit=11)
        else:
            result = select(*args, metric_limit=11, prior=history, stats=stats)
        self.assertEqual(result.evaluations, len(observations))
        self.assertLessEqual(result.evaluations, 11)
        return result, observations, stats

    def test_prefers_a_cached_miss_already_passed_by_another_prompt(self):
        history = {'2': {'incumbent': False}, '3': {'incumbent': False, 'previous': True}}
        result, reads, stats = self.screen(history)
        self.assertEqual(result.prompt, 'second')
        self.assertEqual(reads[:3], [('incumbent', '0'), ('first', '0'), ('second', '3')])
        self.assertEqual(stats['alternateFinalists'], 1)

    def test_no_second_cached_miss_preserves_the_existing_screen(self):
        original, _, _ = self.screen({}, baseline=True)
        same, reads, stats = self.screen({'0': {'incumbent': False}})
        self.assertEqual(same, original)
        self.assertEqual(reads, [('incumbent', '0'), ('first', '0'), ('second', '0')])
        self.assertEqual(stats['alternateProbes'], 0)

    def test_reusing_a_failed_cached_probe_buys_no_incumbent_scan(self):
        result, reads, _ = self.screen({'2': {'incumbent': False}})
        self.assertEqual(result.prompt, 'incumbent')
        self.assertEqual(reads, [('incumbent', '0'), ('first', '0'), ('second', '2')])
