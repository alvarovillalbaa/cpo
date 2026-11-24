from functools import partial

import pytest

from cpo import Observation, Row
from cpo.quoted_shared_validation_cycle import _screen as quoted_screen
from cpo.switch_validation_case import screen
from cpo.two_sided_certificate_cycle import _run


ROSTER = tuple('abcdefgh')
ROWS = (Row('first', 'validation'), Row('second', 'validation'), Row('third', 'validation'))


def execute(search, grades, *, cap=9, rows=ROWS):
    reads = []

    def evaluate(prompt, row):
        cell = prompt, row.id
        assert cell not in reads
        reads.append(cell)
        return Observation(cell in grades, {})

    result, evidence = search('base', ROSTER, rows, evaluate, cap)
    assert len(reads) == result.evaluations <= cap
    return result, evidence, reads


@pytest.mark.parametrize('passes', ({('base', 'first')}, {('b', 'first')}))
def test_incumbent_pass_or_early_repair_matches_the_original_quote(passes):
    baseline = execute(partial(quoted_screen, halve=True), passes)
    assert execute(partial(screen, initial_probes=2, unopened_first=True), passes) == baseline


@pytest.mark.parametrize('unopened', (False, True))
def test_second_miss_switches_cases_and_uses_the_selected_roster_order(unopened):
    passes = {('c', 'second'), ('a', 'second')}
    result, counts, reads = execute(partial(screen, initial_probes=2, unopened_first=unopened), passes)
    winner = 'c' if unopened else 'a'
    assert result.finalist == winner
    assert counts == ((0, 1), (1, 1))
    assert reads == [('base', 'first'), ('a', 'first'), ('b', 'first'),
                     ('base', 'second'), (winner, 'second')]


def test_second_pass_resumes_the_opening_case_with_one_less_probe():
    search = partial(screen, initial_probes=2, unopened_first=True)
    result, _, reads = execute(search, {('base', 'second'), ('h', 'first')})
    assert result.prompt == 'base'
    assert reads == [('base', 'first'), ('a', 'first'), ('b', 'first'), ('base', 'second'),
                     *((prompt, 'first') for prompt in 'cdefg')]


@pytest.mark.parametrize('count', (2, 4, 6))
def test_all_failures_spend_only_the_original_cap(count):
    result, _, reads = execute(partial(screen, initial_probes=count, unopened_first=True), set())
    assert result.prompt == 'base'
    assert reads[count + 1] == ('base', 'second')
    assert len(reads) == 9


@pytest.mark.parametrize('cap,rows', ((8, ROWS), (14, ROWS), (9, ROWS[:1]),
                                      (9, (*ROWS[:2], Row('third', 'validation', critical=True)))))
def test_critical_cases_and_other_funding_match_the_original_quote(cap, rows):
    grades = {('base', 'second'), ('c', 'first'), ('c', 'second'), ('c', 'third')}
    baseline = execute(partial(quoted_screen, halve=True), grades, cap=cap, rows=rows)
    assert execute(partial(screen, initial_probes=2, unopened_first=True), grades, cap=cap, rows=rows) == baseline


def test_a_second_case_nominee_needs_independent_qualification():
    search = partial(screen, initial_probes=2, unopened_first=True)
    result = _run('base', ROSTER, ROWS, (Row('q', 'qualification'),),
                  lambda prompt, row: Observation(prompt == 'c' and row.id == 'second', {}),
                  metric_limit=9, qualify=lambda *_: False, screen=search)
    assert result.search.finalist == 'c'
    assert result.prompt == 'base'
