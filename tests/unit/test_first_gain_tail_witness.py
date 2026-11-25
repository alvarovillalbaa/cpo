from itertools import product

import pytest

from benchmarks import first_gain_validation_width as fixed
from benchmarks.first_gain_tail_witness import has_repair, screen
from cpo import Observation, Row


def test_only_same_case_grades_count_and_balance_is_prompt_specific():
    base = {'r1': False, 'r2': True, 'r3': True}
    unbalanced = {'r1': True, 'r2': False, 'r3': False}
    assert not has_repair(base, ({'unknown': True}, {'r2': True}), balanced=False)
    assert has_repair(base, (unbalanced,), balanced=False)
    assert not has_repair(base, (unbalanced,), balanced=True)
    assert has_repair(base, ({'r1': True, 'r2': False}, {'r3': False}), balanced=True)


@pytest.mark.parametrize('policy', ('repair', 'balanced', 'scout'))
def test_witness_gate_preserves_short_nominees_and_full_panel_certificates(policy):
    prompts = ('base', 'a', 'b')
    rows = tuple(Row(f'v{index}', 'validation') for index in range(4))

    def play(board, method, setting):
        paid = {name: {} for name in prompts}

        def evaluate(prompt, row):
            index = rows.index(row)
            assert index not in paid[prompt]
            grade = board[prompts.index(prompt)][index]
            paid[prompt][index] = grade
            return Observation(grade, {})

        result, _ = method(setting, prompts[0], prompts[1:], rows, evaluate, 19,
                           prepaid={row.id for row in rows[:2]}, read_limit=18)
        assert result.evaluations == sum(map(len, paid.values()))
        return result, paid

    rescued = retained = 0
    for grades in product((False, True), repeat=12):
        board = tuple(grades[index:index + 4] for index in range(0, 12, 4))
        short, prefix = play(board, fixed.screen, 3)
        actual, paid = play(board, screen, policy)
        assert 0 <= actual.evaluations - short.evaluations <= 6
        if short.finalist:
            assert (actual, paid) == (short, prefix)
            continue
        if not has_repair(prefix['base'], (prefix['a'], prefix['b']), balanced=policy == 'balanced'):
            if policy != 'scout':
                assert (actual, paid) == (short, prefix)
            retained += 1
        if actual.finalist:
            assert sum(board[prompts.index(actual.finalist)]) > sum(board[0])
            rescued += 1
    assert rescued and retained
