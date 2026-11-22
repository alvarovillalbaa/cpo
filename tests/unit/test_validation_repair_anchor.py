import pytest

from benchmarks.validation_repair_anchor import gepa_bounds, repair_screen
from cpo import Observation, Row


@pytest.mark.parametrize('repairs,cap,winner,paid', [(1, 8, 'seeded', 3), (4, 5, 'seeded', 4), (4, 6, 'other', 6)])
def test_repair_cut_reuses_paid_incumbent_pass_and_funds_whole_followup(repairs, cap, winner, paid):
    rows = tuple(Row(name, 'validation') for name in ('pass', 'miss'))
    outcomes = {('base', 'pass'), ('seeded', 'miss'), ('other', 'miss'), ('other', 'pass')}
    calls = []

    def grade(prompt, row):
        key = prompt, row.id
        assert key not in calls
        calls.append(key)
        return Observation(key in outcomes, {})

    result, counts = repair_screen('base', ('seeded', 'other'), rows, grade, cap, repairs=repairs)
    assert result.finalist == winner
    assert result.evaluations == len(calls) == paid
    assert calls[:2] == [('base', 'pass'), ('base', 'miss')]
    assert counts == (((1, 2), (2, 2)) if winner == 'other' else ((0, 1), (1, 1)))


def test_perfect_incumbent_does_not_buy_any_challenger_reply():
    rows = tuple(Row(str(i), 'validation') for i in range(6))

    def grade(prompt, row):
        assert prompt == 'base'
        return Observation(True, {})

    result, counts = repair_screen('base', ('other',), rows, grade, 19, repairs=4)
    assert result.prompt == 'base'
    assert result.evaluations == len(rows)
    assert counts is None


def test_budget_bounds_use_only_attainable_points_and_applicable_ceilings():
    comparable = {'one': {'splitSafeCombined': {'holdoutPasses': 50, 'paidLookups': 43}, 'cpo': {'paidLookups': 49}},
                  'two': {'splitSafeCombined': {'holdoutPasses': 45, 'paidLookups': 29}, 'cpo': {'paidLookups': 35}}}
    assert gepa_bounds(comparable, 40, 35) == {'lowerPasses': 45, 'upperPasses': 45}
    assert gepa_bounds(comparable, 40, 37) == {'lowerPasses': 45, 'upperPasses': 50}
    assert gepa_bounds(comparable, 40, 51) == {'lowerPasses': 50, 'upperPasses': None}
