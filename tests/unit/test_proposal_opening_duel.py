from collections import Counter
from unittest import TestCase

from benchmarks.proposal_opening_duel import engine, opening_order
from cpo import Observation, ProposalPair, Row


class ProposalOpeningDuelTests(TestCase):
    def setUp(self):
        self.rows = [Row(str(i), 'task') for i in range(4)]
        self.pair = ProposalPair('rewrite', 'repair')
        self.known = {'start': '1000', 'rewrite': '1000', 'repair': '0111'}
        self.calls = []

    def observe(self, prompt, row):
        self.calls.append((prompt, row.id))
        return Observation(self.known[prompt][int(row.id)] == '1', {})

    def test_miss_and_pass_duel_uses_stratum_sizes(self):
        chosen, cost = opening_order('start', self.rows, self.observe, self.pair, policy='paired')
        self.assertEqual(chosen, ProposalPair('repair', 'rewrite'))
        self.assertEqual(cost, 4)
        self.assertEqual(self.calls[4:], [('rewrite', '1'), ('rewrite', '0'), ('repair', '1'), ('repair', '0')])

    def test_control_buys_same_replies_and_keeps_original_order(self):
        order, cost = opening_order('start', self.rows, self.observe, self.pair, policy='matched')
        self.assertIs(order, self.pair)
        self.assertEqual(cost, 4)

    def test_perfect_incumbent_skips_probe(self):
        self.known['start'] = '1111'
        order, cost = opening_order('start', self.rows, self.observe, self.pair, policy='paired')
        self.assertIs(order, self.pair)
        self.assertEqual(cost, 0)
        self.assertTrue(all(prompt == 'start' for prompt, _ in self.calls))

    def test_paid_probe_reuse_keeps_actual_calls_within_cap(self):
        counters = Counter()
        chosen = engine('paired', counters)(
            'start', [Row('train', 'task')], self.rows, self.observe,
            lambda *_: self.fail('The precomputed pair must supply its only round'),
            opening_pair=self.pair, metric_limit=12, rounds=1, train_per_round=1, seed=11, adaptive=True,
        )
        self.assertEqual(chosen.prompt, 'repair')
        self.assertEqual(counters['openingSwaps'], 1)
        self.assertGreater(counters['probesReused'], 0)
        self.assertEqual(chosen.evaluations, len(set(self.calls)))
        self.assertEqual(len(self.calls), chosen.evaluations)
        self.assertLessEqual(chosen.evaluations, 12)
