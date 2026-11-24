"""T2 checks for certified read savings, budget and independent proof."""

from functools import partial

import pytest

from cpo import Observation, Row
from cpo.reinvested_shared_validation_cycle import _screen, run_reinvested_shared_validation_cycle
from cpo.two_sided_certificate_cycle import _run, run_two_sided_certificate_cycle


def test_saved_slots_fund_more_shared_rows_before_exact_qualification():
    roster = tuple(f'p{i}' for i in range(8))
    validation = tuple(Row(f'v{i}', 'validation') for i in range(6))
    qualification = (Row('q', 'qualification'),)

    def exercise(cycle, cap, accepted):
        paid = set()

        def observe(prompt, row):
            assert row in validation
            assert (prompt, row.id) not in paid
            paid.add((prompt, row.id))
            return Observation(prompt != 'base' and (prompt != 'p0' or row.id == 'v0'), {})

        def qualify(prompt, row, repeat):
            assert row in qualification and repeat == 0
            return prompt == accepted

        result = cycle('base', roster, validation, qualification, observe, metric_limit=cap, qualify=qualify)
        return result, paid

    quoted = partial(_run, screen=partial(_screen, reinvest=False))
    original, old_paid = exercise(quoted, 13, 'p1')
    assert original.search.finalist == 'p0'
    assert original.prompt == 'base'
    assert {row for prompt, row in old_paid if prompt == 'base'} == {'v0'}

    winner, paid = exercise(run_reinvested_shared_validation_cycle, 13, 'p1')
    assert winner.search.finalist == winner.prompt == 'p1'
    assert len(paid) == winner.search.evaluations <= 13
    assert {row for prompt, row in paid if prompt == 'base'} > {'v0'}
    rejected, _ = exercise(run_reinvested_shared_validation_cycle, 13, None)
    assert rejected.search.finalist == 'p1' and rejected.prompt == 'base'


def test_critical_validation_falls_back_to_strict():
    validation = (Row('miss', 'validation'), Row('guard', 'validation', critical=True))
    qualification = (Row('q', 'qualification'),)

    def exercise(cycle):
        rows = []

        def evaluate(prompt, row):
            rows.append((prompt, row.id))
            return Observation(prompt == 'safe' or prompt == 'base' and row.critical, {})

        result = cycle('base', ('unsafe', 'safe'), validation, qualification, evaluate,
                       metric_limit=8, qualify=lambda prompt, *_: prompt == 'safe')
        return result, rows

    strict, strict_rows = exercise(run_two_sided_certificate_cycle)
    assert strict.prompt == 'safe'
    assert exercise(run_reinvested_shared_validation_cycle) == (strict, strict_rows)


def test_budget_quotes_every_slot_before_buying_a_round():
    validation = tuple(Row(str(i), 'validation') for i in range(6))
    qualification = (Row('q', 'qualification'),)
    roster = tuple(f'p{i}' for i in range(8))

    def observe(*_):
        pytest.fail('The first shared round costs nine slots and must not start')

    result = run_reinvested_shared_validation_cycle('base', roster, validation, qualification, observe,
                                                    metric_limit=8, qualify=lambda *_: False)
    assert result.prompt == 'base' and result.search.evaluations == 0
