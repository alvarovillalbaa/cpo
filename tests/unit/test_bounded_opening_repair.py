from functools import partial

import pytest

from benchmarks.bounded_opening_repair_transfer import choose
from cpo import Observation, Row
from cpo.bounded_opening_repair import screen
from cpo.quoted_shared_validation_cycle import _screen as quoted_screen
from cpo.second_row_validation import screen as second_row_screen


ROSTER = tuple('abcdefgh')
ROWS = (Row('first', 'validation'), Row('second', 'validation'), Row('third', 'validation'))


def run(search, passes, *, rows=ROWS, cap=9):
    seen = []

    def evaluate(prompt, row):
        key = prompt, row.id
        assert key not in seen
        seen.append(key)
        return Observation(key in passes, {})

    result, evidence = search('base', ROSTER, rows, evaluate, cap)
    assert result.evaluations == len(seen) <= cap
    return result, evidence, seen


@pytest.mark.parametrize('repair', (False, True))
@pytest.mark.parametrize('winner', ('b', 'g'))
def test_opening_miss_limits_the_challengers_without_buying_a_second_case(repair, winner):
    rule = partial(screen, repair=repair, opening_width=4)
    result, _, paid = run(rule, {(winner, 'first')})
    assert result.prompt == ('b' if winner == 'b' else 'base')
    expected = 'ab' if winner == 'b' else 'abcd'
    assert paid == [(prompt, 'first') for prompt in ('base', *expected)]


@pytest.mark.parametrize('width', (2, 4, 6))
def test_opening_pass_keeps_the_full_second_case_roster(width):
    passes = {('base', 'first'), ('f', 'second')}
    expected = run(partial(second_row_screen, preserve_first=False), passes)
    assert expected[0].finalist == 'f'
    assert run(partial(screen, repair=True, opening_width=width), passes) == expected


@pytest.mark.parametrize('repair', (False, True))
@pytest.mark.parametrize('cap,rows', ((8, ROWS), (14, ROWS),
                                      (9, (*ROWS[:2], Row('third', 'validation', critical=True)))))
def test_original_screen_handles_other_funding_and_critical_cases(repair, cap, rows):
    passes = {('base', 'second'), ('g', 'first'), ('g', 'second'), ('g', 'third')}
    expected = run(partial(quoted_screen, halve=True), passes, rows=rows, cap=cap)
    assert run(partial(screen, repair=repair, opening_width=4), passes, rows=rows, cap=cap) == expected


def test_choose_honors_each_cap_and_keeps_the_baseline_on_exact_ties():
    points = {
        ('baseline',): {'a': {'holdoutPasses': 3, 'paidLookups': 2}, 'b': {'holdoutPasses': 2, 'paidLookups': 2}},
        ('alternate',): {'a': {'holdoutPasses': 3, 'paidLookups': 2}, 'b': {'holdoutPasses': 2, 'paidLookups': 2}},
        ('overspend',): {'a': {'holdoutPasses': 9, 'paidLookups': 3}, 'b': {'holdoutPasses': 9, 'paidLookups': 1}},
    }
    result = choose(points, {'a': 2, 'b': 2}, ('baseline',))
    assert result['actions'] == ('baseline',)
    assert result['feasibleTables'] == 2
