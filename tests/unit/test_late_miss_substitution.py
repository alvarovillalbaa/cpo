from collections import Counter
from unittest import TestCase

from benchmarks.late_miss_substitution import select
from cpo import Observation, Row
from cpo.lazy_incumbent import select_with_lazy_incumbent


class LateMissSubstitutionTests(TestCase):
    def screen(self, incumbent, replies, *, baseline=False):
        rows = [Row(str(i), 'task') for i in range(len(incumbent))]
        prompts = tuple(str(i) for i in range(len(replies)))
        matrix = {'incumbent': incumbent, **dict(zip(prompts, replies, strict=True))}
        reads, stats = [], Counter()

        def evaluate(prompt, row):
            self.assertNotIn((prompt, row.id), reads)
            reads.append((prompt, row.id))
            return Observation(matrix[prompt][int(row.id)] == '1', {})

        cap = 2 * len(rows) - 1 + len(prompts)
        if baseline:
            result = select_with_lazy_incumbent('incumbent', prompts, rows, evaluate, metric_limit=cap)
        else:
            result = select('incumbent', prompts, rows, evaluate, metric_limit=cap, stats=stats)
        self.assertEqual(result.evaluations, len(reads))
        self.assertLessEqual(result.evaluations, cap)
        return result, reads, stats

    def test_trade_tail_probe_even_if_the_incumbent_passes_the_new_case(self):
        replies = ['0000'] * 7
        _, baseline, _ = self.screen('0110', replies, baseline=True)
        result, reads, stats = self.screen('0110', replies)
        self.assertEqual(result.prompt, 'incumbent')
        self.assertEqual(set(reads), (set(baseline) - {('6', '0')}) | {('incumbent', '2')})
        self.assertEqual(stats['tailProbesSubstituted'], 1)

    def test_give_the_fifth_challenger_the_alternate_miss(self):
        result, reads, stats = self.screen('0101', ['0000'] * 4 + ['0111'] + ['0000'] * 2)
        self.assertEqual(result.prompt, '4')
        self.assertEqual(reads[:7], [('incumbent', '0'), ('0', '0'), ('1', '0'), ('2', '0'), ('3', '0'),
                                     ('incumbent', '2'), ('4', '2')])
        self.assertEqual(stats['alternateFinalists'], 1)

    def test_an_early_winner_uses_the_original_proof(self):
        replies = ['0000', '1111'] + ['0000'] * 5
        original = self.screen('0101', replies, baseline=True)
        treatment = self.screen('0101', replies)
        self.assertEqual(original[:2], treatment[:2])
        self.assertEqual(treatment[2]['tailProbesSubstituted'], 0)
