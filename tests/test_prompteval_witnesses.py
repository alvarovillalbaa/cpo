import unittest

from benchmarks import prompteval_witnesses as witnesses


class WitnessSelectionTests(unittest.TestCase):
    def test_weights_avoid_trading_away_the_incumbents_common_passes(self):
        incumbent, repair, replacement = 'base', 'trade', 'preserve'
        candidates = [incumbent, repair, replacement]
        correct = {incumbent: {1}, repair: {9}, replacement: {1, 9}}
        observe = lambda prompt, row: row in correct[prompt]
        self.assertEqual(witnesses.weighted_shortlist(candidates[:2], [1, 2, 3], [9], observe), [incumbent])
        self.assertEqual(witnesses.weighted_shortlist(candidates, [1, 2, 3], [9], observe),
                         [incumbent, replacement])

    def test_witness_pass_does_not_skip_full_validation(self):
        trial = {'candidates': ['0', '1'], 'train': list(range(12)), 'validation': list(range(12, 36))}
        baseline = '0' * 12 + '0' + '1' * 23 + '0'
        loses_other_rows = '0' * 12 + '11' + '0' * 22 + '1'
        result = witnesses.evaluate_strategy(witnesses.WEIGHTED, [baseline, loses_other_rows], trial, [36])
        self.assertEqual(result['candidate'], '0')
        self.assertEqual(result['holdoutPasses'], 0)
        self.assertLessEqual(result['evaluations'], witnesses.transfer.LOOKUP_LIMIT)
        with self.assertRaisesRegex(ValueError, 'disjoint from qualification'):
            witnesses.evaluate_strategy(witnesses.WEIGHTED, [baseline, loses_other_rows], trial, [12])


if __name__ == '__main__':
    unittest.main()
