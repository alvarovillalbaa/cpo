from functools import partial

import pytest

from cpo import Observation, Row
from cpo.quoted_shared_validation_cycle import _screen as quoted_screen
from cpo.second_row_validation import screen
from cpo.two_sided_certificate_cycle import _run


ROSTER = tuple('abcdefgh')
ROWS = (Row('first', 'validation'), Row('second', 'validation'), Row('third', 'validation'))


def execute(search, grades, *, cap=9, rows=ROWS):
    ledger = []

    def read(prompt, row):
        cell = prompt, row.id
        assert cell not in ledger
        ledger.append(cell)
        return Observation(grades.get(cell, False), {})

    selection, counts = search('base', ROSTER, rows, read, cap)
    assert len(ledger) == selection.evaluations <= cap
    return selection, counts, ledger


@pytest.mark.parametrize('preserve', (False, True))
@pytest.mark.parametrize('cap,rows', ((8, ROWS), (9, ROWS[:1]), (14, ROWS),
                                      (9, (Row('first', 'validation', critical=True), *ROWS[1:]))))
def test_other_funding_and_critical_cases_reproduce_quoted_path(preserve, cap, rows):
    grades = {('base', 'first'): True, ('a', 'second'): True}
    baseline = execute(partial(quoted_screen, halve=True), grades, cap=cap, rows=rows)
    assert execute(partial(screen, preserve_first=preserve), grades, cap=cap, rows=rows) == baseline


@pytest.mark.parametrize('preserve', (False, True))
def test_failed_first_row_preserves_original_nominee_and_read_order(preserve):
    grades = {('b', 'first'): True, ('base', 'second'): True}
    assert execute(partial(screen, preserve_first=preserve), grades) == execute(partial(quoted_screen, halve=True), grades)


@pytest.mark.parametrize('preserve', (False, True))
def test_two_incumbent_passes_pay_no_challenger_reads(preserve):
    result, _, reads = execute(partial(screen, preserve_first=preserve),
                               {('base', 'first'): True, ('base', 'second'): True})
    assert result.prompt == 'base'
    assert reads == [('base', 'first'), ('base', 'second')]


@pytest.mark.parametrize('hold_first', (False, True))
def test_guard_requires_both_first_and_second_case_passes(hold_first):
    grades = {('base', 'first'): True, ('a', 'second'): True, ('a', 'first'): hold_first}
    relaxed, counts, _ = execute(partial(screen, preserve_first=False), grades)
    guarded, guarded_counts, reads = execute(partial(screen, preserve_first=True), grades)
    assert relaxed.prompt == 'a'
    assert counts == ((0, 1), (1, 1))
    assert ('a', 'first') in reads
    assert guarded.prompt == ('a' if hold_first else 'base')
    assert guarded_counts == (((1, 2), (2, 2)) if hold_first else None)


def test_recovered_nominee_can_still_fail_independent_qualification():
    qualification = (Row('q', 'qualification'),)
    witnessed = {('base', 'first'), ('a', 'first'), ('a', 'second')}
    result = _run('base', ROSTER, ROWS, qualification,
                  lambda prompt, row: Observation((prompt, row.id) in witnessed, {}),
                  metric_limit=9, qualify=lambda *_: False, screen=partial(screen, preserve_first=True))
    assert result.search.finalist == 'a'
    assert result.prompt == 'base'
