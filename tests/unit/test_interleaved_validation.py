from functools import partial

import pytest

from benchmarks.interleaved_validation_transfer import channel
from cpo import Observation, Row
from cpo.interleaved_validation_cases import screen
from cpo.switch_validation_case import screen as fixed_switch


ROWS = (Row('first', 'validation'), Row('second', 'validation'), Row('third', 'validation'))
ROSTER = tuple('abcdefgh')


def run(search, passes, *, cap=9, rows=ROWS):
    paid = []

    def evaluate(prompt, row):
        key = prompt, row.id
        assert key not in paid
        paid.append(key)
        return Observation(key in passes, {})

    result, counts = search('base', ROSTER, rows, evaluate, cap)
    assert len(paid) == result.evaluations <= cap
    return result, counts, paid


@pytest.mark.parametrize('second_first', (False, True))
def test_two_failed_cases_alternate_in_unopened_roster_order(second_first):
    result, _, paid = run(partial(screen, second_first=second_first), set())
    assert result.finalist is None
    assert paid[:4] == [('base', 'first'), ('a', 'first'), ('b', 'first'), ('base', 'second')]
    cases = ('second', 'first') if second_first else ('first', 'second')
    assert paid[4:] == [('c', cases[0]), ('c', cases[1]), ('d', cases[0]), ('d', cases[1]), ('e', cases[0])]


@pytest.mark.parametrize('second_first', (False, True))
def test_opening_case_repair_is_recoverable_after_two_failures(second_first):
    passes = {('c', 'first')}
    baseline = run(partial(fixed_switch, initial_probes=2, unopened_first=True), passes)
    assert baseline[0].finalist is None
    result, counts, _ = run(partial(screen, second_first=second_first), passes)
    assert result.finalist == 'c'
    assert counts == ((0, 1), (1, 1))


@pytest.mark.parametrize('passes', ({('base', 'first')}, {('a', 'first')}, {('base', 'second'), ('g', 'first')}))
def test_first_pass_early_repair_or_second_pass_preserves_the_fixed_switch_path(passes):
    assert run(partial(screen, second_first=True), passes) == run(
        partial(fixed_switch, initial_probes=2, unopened_first=True), passes)


@pytest.mark.parametrize('cap,rows', ((8, ROWS), (14, ROWS), (9, ROWS[:1]),
                                      (9, (*ROWS[:2], Row('third', 'validation', critical=True)))))
def test_inapplicable_or_critical_panel_uses_the_same_fallback(cap, rows):
    passes = {('g', 'first'), ('g', 'second')}
    assert run(partial(screen, second_first=False), passes, cap=cap, rows=rows) == run(
        partial(fixed_switch, initial_probes=2, unopened_first=True), passes, cap=cap, rows=rows)


def test_attribution_uses_a_paid_repair_and_rejects_unobserved_evidence():
    assert channel('base', 'a', 'a', {}, (0, 1)) == 'same-deployment'
    assert channel('base', 'a', 'base', {}, (0, 1)) == 'lost-opening-repair'
    assert channel('base', 'a', 'b', {('validation', 'b', '0'): True}, (0, 1)) == 'replaced-with-opening-repair'
    assert channel('base', 'base', 'b', {('validation', 'b', '1'): True}, (0, 1)) == 'added-second-case-repair'
    with pytest.raises(ValueError, match='paid validation repair'):
        channel('base', 'base', 'b', {('qualification', 'b', '1'): True}, (0, 1))
