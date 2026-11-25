from itertools import product
from unittest import TestCase

from benchmarks import first_gain_precheck_stopping as study
from cpo import Row


class StoppingPrecheckTests(TestCase):
    def test_same_case_votes_change_the_conditional_prior(self):
        self.assertEqual(study.pass_probability((2, 2, 0), 2, 1), 0.5)
        self.assertEqual(study.pass_probability((2, 2, 0), 2, 5), 5 / 6)
        self.assertEqual(study.pass_probability((1, 1, 0), 2, 5), 1 / 6)
        self.assertEqual(study.pass_probability((1, 2, 0), 2, 5), 0.5)

    def test_fallback_wins_when_the_expected_cost_is_a_tie(self):
        board = ((1, 1, 2), (2, 1, 0))
        self.assertEqual(study.choose_read(board, 2, 5), (2.0, None, None))
        self.assertEqual(study.choose_read(board, 3, 5), (2.5, (2, 1, 0), 2))

    def test_exhaustive_four_case_boards_never_certify_a_possible_gain(self):
        rows = tuple(Row(str(index), 'proof') for index in range(4))
        certified = deferred = 0
        for bits in product((False, True), repeat=12):
            scores = [sum(bits[offset:offset + 4]) for offset in (0, 4, 8)]
            visited = set()

            def observe(side, row):
                index = 4 * side + int(row.id)
                self.assertNotIn(index, visited)
                visited.add(index)
                return bits[index]

            state = study.initial_board(8, 5, rows, observe, allowance=12, trigger=0)
            self.assertLessEqual(len(visited), 12)
            if state is None:
                deferred += 1
            else:
                self.assertGreaterEqual(scores[0], max(scores[1:]))
                self.assertLessEqual(max(study.earlier.upper_margins(4, state)), 0)
                certified += 1
        self.assertGreater(certified, 0)
        self.assertGreater(deferred, 0)
