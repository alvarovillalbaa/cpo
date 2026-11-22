import pytest

from cpo import Observation, Row
from cpo.sequential_certificate_cycle import _screen as screen, run_sequential_certificate_cycle


def test_successful_probe_proves_critical_pass_before_opening_another_prompt():
    rows = (Row('miss', 'task'), Row('critical', 'task', critical=True))
    called = []

    def evaluate(prompt, row):
        called.append((prompt, row.id))
        return Observation(row.critical or prompt == 'first', {})

    decision, counts = screen('start', ('first', 'second'), rows, evaluate, 4)
    assert decision.prompt == 'first'
    assert counts == ((1, 2), (2, 2))
    assert called == [('start', 'miss'), ('start', 'critical'), ('first', 'miss'), ('first', 'critical')]


def test_a_repaired_miss_does_not_override_a_critical_regression():
    rows = (Row('miss', 'task'), Row('critical', 'task', critical=True))
    called = []

    def evaluate(prompt, row):
        called.append((prompt, row.id))
        passed = {
            'start': row.critical,
            'first': not row.critical,
            'second': True,
        }
        return Observation(passed[prompt], {})

    decision, _ = screen('start', ('first', 'second'), rows, evaluate, 6)
    assert decision.prompt == 'second'
    assert called[-4:] == [('first', 'miss'), ('first', 'critical'), ('second', 'miss'), ('second', 'critical')]


def test_a_probe_failure_can_still_fund_an_exact_certificate():
    rows = tuple(Row(str(index), 'task') for index in range(3))
    called = []

    def evaluate(prompt, row):
        called.append((prompt, row.id))
        return Observation(row.id == '2' or (prompt == 'first' and row.id == '1'), {})

    decision, counts = screen('start', ('first',), rows, evaluate, 6)
    assert decision.prompt == 'first'
    assert counts == ((1, 3), (2, 3))
    assert called[-3:] == [('first', '0'), ('first', '1'), ('first', '2')]


def test_independent_precheck_can_skip_search_without_another_paid_reply():
    validation = (Row('validation', 'task'),)
    proof = tuple(Row(str(index), 'task') for index in range(3))

    def qualify(prompt, row, repeat):
        assert prompt == 'start' and repeat == 0
        return row.id == '0' or row.id == '1'

    result = run_sequential_certificate_cycle(
        'start', ('new',), validation, proof, lambda *_: pytest.fail('The gain is impossible'),
        metric_limit=3, qualify=qualify, minimum_gain=2,
    )
    assert result.prompt == 'start'
    assert result.search.evaluations == 0
    assert result.qualification.upper_gain == 1
    assert result.qualification_evaluations == 2
