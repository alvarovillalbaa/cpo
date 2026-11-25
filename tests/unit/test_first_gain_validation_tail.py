from itertools import product

import pytest

from benchmarks import first_gain_validation_width as fixed
from benchmarks.first_gain_validation_tail import screen
from cpo import Observation, Row


def grade_panel(board, runner, *settings):
    rows = tuple(Row(f'v{index}', 'validation') for index in range(4))
    prompts = ('base', 'a', 'b')
    paid = set()

    def evaluate(prompt, row):
        key = prompts.index(prompt), rows.index(row)
        assert key not in paid
        paid.add(key)
        return Observation(board[key[0]][key[1]], {})

    result = runner(*settings, prompts[0], prompts[1:], rows, evaluate, 19,
                    prepaid={row.id for row in rows[:2]}, read_limit=18)
    assert result[0].evaluations == len(paid)
    return result, paid


@pytest.mark.parametrize('extra', (3, 6, 9))
def test_extension_reuses_paid_grades_and_certifies_full_panel(extra):
    rescued = 0
    for values in product((False, True), repeat=12):
        board = tuple(values[start:start + 4] for start in range(0, 12, 4))
        fixed_result, fixed_reads = grade_panel(board, fixed.screen, 3)
        adaptive, adaptive_reads = grade_panel(board, screen, extra)
        assert fixed_reads <= adaptive_reads
        assert len(adaptive_reads - fixed_reads) <= extra
        if fixed_result[0].finalist:
            assert (adaptive, adaptive_reads) == (fixed_result, fixed_reads)
        elif adaptive[0].finalist:
            side = ('base', 'a', 'b').index(adaptive[0].finalist)
            assert sum(board[side]) > sum(board[0])
            assert adaptive[1] == tuple((sum(board[s][row] for index, row in adaptive_reads if s == index),
                                         sum(index == s for index, _ in adaptive_reads)) for s in (0, side))
            rescued += 1
    assert rescued > 0


def test_full_panel_bound_can_stop_without_buying_tail_grades():
    board = ((True,) * 4, (False,) * 4, (False,) * 4)
    fixed_result = grade_panel(board, fixed.screen, 3)
    assert fixed_result[0][0].finalist is None
    assert grade_panel(board, screen, 3) == fixed_result
