"""T2 mock grades for the fixed-roster three-cycle controls."""

from functools import partial

from benchmarks.continuous_search_controls import HALVING, UNIFORM, screen, settings
from cpo.optimizer import Observation, Row
from cpo.two_sided_certificate_cycle import _run


def test_controls_compare_complete_rounds_with_the_same_incumbent():
    grades = {'base': (0, 1), 'a': (1, 1), 'b': (1, 0), 'c': (0, 1), 'd': (0, 1)}
    rows = (Row('0', 'validation'), Row('1', 'validation'))
    roster = ('a', 'b', 'c', 'd')
    ledger = []

    def evaluate(prompt, row):
        ledger.append((prompt, row.id))
        return Observation(bool(grades[prompt][int(row.id)]), {})

    selection, counts = screen('base', roster, rows, evaluate, 8, mode=HALVING, width=4)
    assert ledger == [(prompt, '0') for prompt in ('base', *roster)] + [
        (prompt, '1') for prompt in ('base', 'a', 'b')]
    assert (selection.finalist, selection.evaluations, counts) == ('a', 8, ((1, 2), (2, 2)))

    ledger.clear()
    selection, counts = screen('base', roster, rows, evaluate, 9, mode=UNIFORM, width=4)
    assert ledger == [(prompt, '0') for prompt in ('base', *roster)]
    assert (selection.finalist, selection.evaluations, counts) == ('a', 5, ((0, 1), (1, 1)))


def test_tied_validation_retains_start_and_independent_qualification_rejects_false_gain():
    rows = (Row('validation', 'validation'),)
    roster = ('a', 'b')

    def evaluate(prompt, row):
        return Observation(True, {})

    selection, counts = screen('base', roster, rows, evaluate, 3, mode=HALVING, width=4)
    assert (selection.prompt, selection.finalist, counts) == ('base', None, None)

    def challenger_wins(prompt, row):
        return Observation(prompt != 'base', {})

    result = _run('base', roster, rows, (Row('proof', 'qualification'),), challenger_wins, metric_limit=3,
                  qualify=lambda prompt, row, repeat: False, screen=partial(screen, mode=HALVING, width=4))
    assert result.search.finalist == 'a'
    assert result.prompt == 'base'


def test_sealed_sweep_covers_each_completed_row_prefix():
    grid = list(settings(6))
    assert len(grid) == len({name for name, _, _, _ in grid}) == 24
    assert [cap for _, mode, width, cap in grid if mode == HALVING and width == 8] == [9, 14, 17, 20, 22, 24]
    assert [cap for _, mode, width, cap in grid if mode == UNIFORM and width == 4] == [6, 10, 15, 20, 25, 30]
