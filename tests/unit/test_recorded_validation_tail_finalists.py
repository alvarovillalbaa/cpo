from collections import Counter
from itertools import product

from benchmarks import recorded_validation_tail_finalists as study
from cpo import Observation, Row


def paid_race(board, rows, width, cap):
    ledger, audit = {}, Counter()

    def observe(prompt, row):
        key = prompt, row.id
        if key not in ledger:
            assert len(ledger) < cap
            ledger[key] = Observation(board[key], {})
        return ledger[key]

    prompts = tuple(dict.fromkeys(prompt for prompt, _ in board))
    winner = study.select_tail(prompts[0], prompts[1:], rows, observe, ledger, cap=cap, width=width, audit=audit)
    return winner, ledger, audit


def test_tail_can_choose_a_partial_challenger_after_full_certification():
    rows = tuple(Row(str(case), 'validation') for case in range(5))
    results = {'start': (0, 0, 0, 0, 0), 'first': (1, 1, 1, 0, 0), 'alternate': (0, 0, 0, 1, 1)}
    board = {(prompt, row.id): bool(result) for prompt, grades in results.items()
             for row, result in zip(rows, grades, strict=True)}
    winner, ledger, audit = paid_race(board, rows, 1, 15)
    assert winner == 'alternate'
    assert audit['comparedPairs'] == audit['tailNominations'] == 1
    assert audit['finalistTailLookups'] == 2
    assert sum(reply.passed for (prompt, _), reply in ledger.items() if prompt == winner) == 2


def test_full_race_can_recover_an_improvement_missed_by_a_perfect_prefix_incumbent():
    rows = tuple(Row(str(case), 'validation') for case in range(3))
    results = {'start': (1, 1, 0), 'other': (1, 1, 1)}
    board = {(prompt, row.id): bool(result) for prompt, grades in results.items()
             for row, result in zip(rows, grades, strict=True)}
    winner, ledger, audit = paid_race(board, rows, 1, 6)
    assert winner == 'other' and audit['fullRaceFallbacks'] == 1
    assert len(ledger) == 6


def test_every_small_funded_board_preserves_strict_full_panel_and_critical_gates():
    prompts = ('start', 'left', 'right')
    rows = (Row('a', 'validation'), Row('b', 'validation', critical=True), Row('c', 'validation'))
    keys = tuple((prompt, row.id) for prompt in prompts for row in rows)
    for grades in product((False, True), repeat=len(keys)):
        board = dict(zip(keys, grades, strict=True))
        target = sum(grades[:3]) + 1
        valid = {prompt for prompt in prompts[1:] if sum(board[prompt, row.id] for row in rows) >= target
                 and (not grades[1] or board[prompt, 'b'])}
        for width, cap in product((1, 2), (3, 6, len(keys))):
            winner, ledger, _ = paid_race(board, rows, width, cap)
            if cap == len(keys):
                assert (winner == 'start') == (not valid)
            if winner != 'start':
                assert winner in valid
                assert sum(reply.passed for (prompt, _), reply in ledger.items() if prompt == winner) >= target
                if grades[1]:
                    assert ledger[winner, 'b'].passed
