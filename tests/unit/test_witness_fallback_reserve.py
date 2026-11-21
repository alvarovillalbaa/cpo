"""T2 checks for predispatch reservations and evidence-only ordering."""

from dataclasses import replace

import pytest

from benchmarks import witness_fallback_reserve as study
from benchmarks.witness_fallback_routing import Opportunity


def item(name, *, cost, passes=1, grades=5, wins=0):
    return Opportunity((name,), passes, 4, grades, wins, (1, 0), cost)


def test_full_reservation_is_required_even_if_the_archived_settlement_would_fit():
    cheap = item('cheap', cost=2)

    def forbidden(*_):
        pytest.fail('The fixed reservation did not fit')

    assert study.fund([cheap], 39, 40, forbidden) == ([], 39)


def test_unused_credit_funds_a_second_episode_then_stops_before_the_third():
    items = [item('first', cost=24), item('second', cost=10), item('third', cost=0)]
    receipts, left = study.fund(items, 64, 40, lambda opportunity: (opportunity.addedLookups, opportunity.deltas))
    assert [row[0] for row in receipts] == [('first',), ('second',)]
    assert [row[1] for row in receipts] == [24, 10]
    assert left == 30


def test_excess_settlement_aborts_before_another_episode():
    selected = []

    def settle(opportunity):
        selected.append(opportunity.key)
        return opportunity.addedLookups, opportunity.deltas

    with pytest.raises(ValueError, match='exceeded its validation and proof reservation'):
        study.fund([item('overrun', cost=41), item('normal', cost=10)], 80, 40, settle)
    assert selected == [('overrun',)]


def test_order_never_inspects_unfunded_outcomes_or_realized_costs():
    rows = [item('weak', cost=20, passes=0, wins=1), item('strong', cost=8, passes=3, grades=7)]
    altered = [replace(row, addedLookups=100 - row.addedLookups, deltas=(-1, -1)) for row in rows]
    for policy in (*study.PAID, *study.BLIND):
        assert [row.key for row in study.order(rows, policy)] == [row.key for row in study.order(altered, policy)]
