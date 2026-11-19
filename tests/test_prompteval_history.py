import unittest

from benchmarks.prompteval_history import PRIMARY, evaluate_cycle, past_score


class PaidHistoryTest(unittest.TestCase):
    def test_prior_excludes_current_validation_and_shrinks_to_even_odds(self):
        self.assertEqual(past_score({}, {0}), 0.5)
        self.assertEqual(past_score({0: False, 1: True}, {0}), 2 / 3)

    def test_repeated_outcomes_are_charged_once_and_exact_selection_is_preserved(self):
        matrix = ['10000', '01011']
        arguments = (matrix, ['0', '1'], [0, 1], [3, 4], 43101)
        history = {'0': {3: False}, '1': {2: False}}
        first = evaluate_cycle(PRIMARY, *arguments, history)
        self.assertEqual(first['candidate'], '0')
        self.assertEqual(first['evaluations'], 5)
        self.assertEqual(first['pastHits'], 1)

        repeated = evaluate_cycle(PRIMARY, *arguments, history)
        self.assertEqual(repeated['candidate'], '0')
        self.assertEqual(repeated['evaluations'], 0)
        self.assertEqual(repeated['pastHits'], 6)

        cold = evaluate_cycle(PRIMARY, *arguments, {})
        self.assertEqual(cold['candidate'], '0')
        self.assertEqual(cold['evaluations'], 6)

    def test_strong_prior_still_requires_strict_validation_gain(self):
        matrix = ['00010', '11110']
        result = evaluate_cycle(PRIMARY, matrix, ['0', '1'], [0, 1], [3, 4], 43101, {'1': {2: True}})
        self.assertEqual(result['candidate'], '0')
        self.assertEqual(result['distinctRequested'], 7)
