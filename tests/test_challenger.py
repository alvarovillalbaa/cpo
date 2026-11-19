from itertools import product

import pytest

from cpo import Observation, Row
from cpo.challenger import certify_challenger


ROWS = tuple(Row(case, 'routing', case == 'critical') for case in ('ordinary', 'critical', 'edge'))


def test_continuation_does_not_retest_cached_rows_or_spend_when_the_budget_cannot_certify():
    incumbent = {'ordinary': True, 'critical': True, 'edge': False}
    checked = []

    def evaluate(row):
        checked.append(row.id)
        return Observation(True, {})

    saved = {'ordinary': True}
    first = certify_challenger(ROWS, incumbent, evaluate, metric_limit=1, observed=saved)
    assert first.status == 'budget' and first.evaluations == 0
    assert first.minimum_fresh_for_promotion == 2
    assert checked == []
    resumed = certify_challenger(ROWS, incumbent, evaluate, metric_limit=2, observed=first.observations)
    assert resumed.status == 'promote' and resumed.evaluations == 2
    assert resumed.minimum_fresh_for_promotion == 0
    assert checked == ['critical', 'edge']
    assert saved == {'ordinary': True}


def test_cached_critical_failure_blocks_promotion_even_with_more_total_passes():
    incumbent = {'ordinary': False, 'critical': True, 'edge': False}
    observed = {'ordinary': True, 'critical': False, 'edge': True}
    result = certify_challenger(ROWS, incumbent, pytest.fail, metric_limit=3, observed=observed)
    assert result.status == 'critical_regression' and result.evaluations == 0
    assert result.minimum_fresh_for_promotion is None


def test_certificates_match_full_validation_when_every_missing_row_can_be_funded():
    for old, new, present in product(product((False, True), repeat=3), repeat=3):
        incumbent = {row.id: flag for row, flag in zip(ROWS, old)}
        complete = {row.id: flag for row, flag in zip(ROWS, new)}
        observed = {row.id: complete[row.id] for row, cached in zip(ROWS, present) if cached}
        expected = sum(new) > sum(old) and (not incumbent['critical'] or complete['critical'])
        for budget in range(len(ROWS) - len(observed) + 1):
            checked = []

            def evaluate(row):
                checked.append(row.id)
                return Observation(complete[row.id], {})

            result = certify_challenger(ROWS, incumbent, evaluate, metric_limit=budget, observed=observed)
            assert result.evaluations == len(checked) <= budget
            assert result.lower_pass_bound <= sum(new) <= result.upper_pass_bound
            assert not set(checked) & observed.keys()
            if result.status == 'promote' or budget == len(ROWS) - len(observed):
                assert (result.status == 'promote') == expected
