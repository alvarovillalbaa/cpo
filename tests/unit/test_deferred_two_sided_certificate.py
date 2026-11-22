from itertools import product

import pytest

from benchmarks.deferred_two_sided_certificate import EXPECTED, ROW, run_trial
from cpo import Observation, Row
from cpo.two_sided_certificate_cycle import _screen, run_two_sided_certificate_cycle


def test_exact_gain_can_certify_with_an_unread_incumbent_case():
    cells = {'start': (0, 0, 0, 1, 0), 'challenger': (1, 1, 1, 1, 1)}
    args = cells, 'start', ('challenger',), ((), (0, 1, 2, 3), (4,), ()), 0, 8, 1
    result, paid = run_trial(ROW, args)

    assert result.prompt == 'challenger'
    assert sum(role == 'validation' and prompt == 'start' for role, prompt, _ in paid) == 3
    assert result.search.evaluations == 5
    assert ('validation', 'start', '3') not in paid


def test_both_orders_enforce_the_cap_exact_gain_and_critical_rows():
    prompts = ('start', 'first', 'second')
    rows = tuple(Row(str(i), 'validation', critical=i == 1) for i in range(3))
    for outcomes in product((False, True), repeat=9):
        cells = dict(zip(prompts, (outcomes[:3], outcomes[3:6], outcomes[6:]), strict=True))
        for cap, expected in product(range(5, 9), (False, True)):
            paid = set()

            def observe(prompt, row):
                assert (prompt, row.id) not in paid
                paid.add((prompt, row.id))
                return Observation(cells[prompt][int(row.id)], {})

            result, counts = _screen('start', prompts[1:], rows, observe, cap, expected=expected)
            assert result.evaluations == len(paid) <= cap
            if result.prompt == 'start':
                assert counts is None
            else:
                assert sum(cells[result.prompt]) > sum(cells['start'])
                assert not cells['start'][1] or cells[result.prompt][1]
                assert sum(total for _, total in counts) <= len(paid)


def test_expected_order_spends_nothing_when_precheck_eliminates_all_challengers():
    cells = {'start': (0, 0, 0, 1), 'challenger': (1, 1, 1, 0)}
    args = cells, 'start', ('challenger',), ((), (0, 1, 2), (3,), ()), 0, 6, 1
    result, paid = run_trial(EXPECTED, args)

    assert result.prompt == 'start'
    assert result.search.evaluations == 0
    assert paid == {('qualification', 'start', '3'): True}


def test_public_cycle_rejects_overlapping_panels_before_calling_evaluator():
    probe = Row('same-case', 'test')
    with pytest.raises(ValueError, match='disjoint'):
        run_two_sided_certificate_cycle('start', ['challenger'], [probe], [probe], None,
                                        metric_limit=4, qualify=None)
