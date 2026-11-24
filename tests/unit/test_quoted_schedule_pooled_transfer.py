"""T2 checks on budget apportionment and independent qualification reserves."""

from benchmarks.quoted_schedule_pooled_transfer import RETAIN, apportion, audit, fit_portfolio, protect_local, search_allowance
from cpo.quoted_shared_validation_cycle import run_quoted_shared_validation_cycle


def test_largest_remainders_apportion_the_entire_calibration_budget():
    assert apportion({'b': 1, 'a': 1, 'c': 2}, 7) == {'a': 2, 'b': 2, 'c': 3}
    assert apportion({'a': 0, 'b': 0}, 0) == {'a': 0, 'b': 0}


def test_allowance_preserves_both_sides_of_independent_qualification():
    assert search_allowance(20, 19, 6, 4) == 12
    assert search_allowance(13, 19, 6, 4) == 0
    assert search_allowance(40, 19, 6, 4) == 19


def test_local_floor_rejects_an_improvement_that_loses_on_one_half():
    points = {'local': {'holdoutPasses': 5, 'paidLookups': 8},
              'lopsided': {'holdoutPasses': 6, 'paidLookups': 7},
              'balanced': {'holdoutPasses': 6, 'paidLookups': 9}}
    scores = {'local': [2, 3], 'lopsided': [4, 2], 'balanced': [3, 3]}
    admitted = protect_local(points, scores, 'local', ((0,), (1,)), 10)
    assert admitted['local'] == points['local']
    assert admitted['balanced'] == points['balanced']
    assert admitted['lopsided']['paidLookups'] == 11


def test_local_floors_can_require_different_settings_in_each_direction():
    banned = {'holdoutPasses': 0, 'paidLookups': 5}
    points = {'a': {RETAIN: banned, 'wide': {'holdoutPasses': 6, 'paidLookups': 3}, 'deep': banned},
              'b': {RETAIN: banned, 'wide': banned, 'deep': {'holdoutPasses': 4, 'paidLookups': 1}}}
    assert fit_portfolio(points, 4) == {'settingsByDirection': {'a': 'wide', 'b': 'deep'},
                                        'holdoutPasses': 10, 'paidLookups': 4}


def test_audit_stops_before_spending_the_unfunded_qualification_reserve():
    plan = {'auditBudget': 6, 'auditSeeds': (1,)}
    cells = {'base': (0, 0, 0), 'winner': (1, 1, 1)}
    cycles = [(1, ('winner',), ((), (0,), (1,), (2,)))]
    inputs = {name: (cells, (2,), (('base', cycles),)) for name in ('left', 'right')}
    measured, vectors = audit(plan, inputs, dict.fromkeys(inputs, 'wide'), {'wide': 2},
                              {'wide': run_quoted_shared_validation_cycle})
    assert measured['totals'] == {'paidLookups': 4, 'holdoutPasses': 1}
    assert measured['unusedLookups'] == 2
    assert sum(v['unfundedCycles'] for v in measured['byDirection'].values()) == 1
    assert sorted(vectors.values()) == [[0], [1]]
