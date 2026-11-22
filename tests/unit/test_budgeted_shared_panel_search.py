import pytest

from benchmarks.budgeted_shared_panel_search import audit_trial, execute_trial
from cpo import Observation, Row
from cpo.shared_validation_cycle import _screen, run_shared_validation_cycle


@pytest.mark.parametrize(('method', 'search_reads', 'width'), (('wide/nonloss', 17, 3), ('deep/nonloss', 18, 5)))
def test_both_schedules_compare_the_nominee_with_the_incumbent_on_identical_cases(method, search_reads, width):
    roster = tuple(f'prompt-{i}' for i in range(8))
    cells = {'start': (1, 1, 1, 1, 1, 1, 0), **{p: (1,) * 7 for p in roster}}
    roles = (), (0, 1, 2, 3, 4, 5), (6,), ()
    result, paid = execute_trial(method, (cells, 'start', roster, roles, 19, 19, 1))

    assert result.prompt == roster[0]
    assert result.search.evaluations == search_reads
    assert audit_trial(cells, 'start', roles, result, paid, 1, method) == width


def test_gain_requirement_keeps_an_incumbent_on_every_measured_tie():
    roster = tuple(f'prompt-{i}' for i in range(8))
    cells = {'start': (1, 1, 1, 1, 1, 1, 0), **{p: (1,) * 7 for p in roster}}
    roles = (), (0, 1, 2, 3, 4, 5), (6,), ()
    result, paid = execute_trial('wide/gain', (cells, 'start', roster, roles, 19, 19, 1))

    assert result.prompt == 'start'
    assert result.search.finalist is None
    assert {prompt for role, prompt, _ in paid if role == 'qualification'} == {'start'}


def test_critical_validation_uses_the_original_strict_screen():
    cells = {'start': (True, False), 'rival': (False, True)}
    rows = Row('0', 'validation', critical=True), Row('1', 'validation')
    result, counts = _screen('start', ('rival',), rows,
                             lambda prompt, row: Observation(cells[prompt][int(row.id)], {}),
                             4, widths=(8, 4, 2), margin=0)

    assert result.prompt == 'start'
    assert counts is None


def test_public_runner_does_not_buy_a_partial_round():
    rows = tuple(Row(str(i), 'validation') for i in range(3))
    qualification = (Row('qualification-case', 'qualification'),)
    candidates = tuple(map(str, range(8)))
    charged = []

    def evaluate(prompt, row):
        charged.append((prompt, row.id))
        return Observation(prompt != 'start', {})

    result = run_shared_validation_cycle('start', candidates, rows, qualification, evaluate,
                                         metric_limit=10, qualify=lambda prompt, row, repeat: prompt != 'start')

    assert result.prompt == '0'
    assert len(charged) == 9
    assert {case for _, case in charged} == {'0'}
