import unittest

from benchmarks.prompteval_proxy import evaluate, qualify


class ProxyReplayTests(unittest.TestCase):
    def test_ranking_uses_only_proxy_training_and_target_decides_promotion(self):
        class TrainingOnly(str):
            def __getitem__(self, row):
                if row not in (0, 1):
                    raise AssertionError('Proxy accessed a case outside its training probes')
                return super().__getitem__(row)

        target = ['0000101', '0000000', '0000111', '0000010']
        proxy = list(map(TrainingOnly, ['0000000', '1100000', '1000000', '0000000']))
        trial = {'candidates': ['0', '1', '2', '3'], 'train': [0, 1, 2, 3], 'validation': [4, 5]}
        result = evaluate('proxy-two', target, proxy, trial, [6])
        self.assertEqual(result['candidate'], '2')
        self.assertEqual(result['targetLookups'], 5)
        self.assertEqual(result['proxyLookups'], 6)
        self.assertEqual(result['holdoutPasses'], 1)
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            evaluate('proxy-two', target, proxy, trial, [4])

    def test_gate_counts_proxy_cost_and_requires_accuracy_preservation(self):
        totals = {'candidate': {'targetLookups': 8, 'proxyLookups': 4, 'holdoutPasses': 12},
                  'reference': {'targetLookups': 10, 'proxyLookups': 0, 'holdoutPasses': 12}}
        self.assertTrue(qualify(totals, 'candidate', 'reference', 1)['qualified'])
        self.assertFalse(qualify(totals, 'candidate', 'reference', 2)['qualified'])
        totals['candidate']['holdoutPasses'] = 11
        self.assertFalse(qualify(totals, 'candidate', 'reference', 1)['qualified'])
