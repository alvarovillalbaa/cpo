"""T2 fixture grades for sparse pricing and case-indexed comparison."""

from collections import Counter

import pytest

from benchmarks.recorded_math_router_transfer import accumulate, record_native


def test_sparse_native_price_boundaries_charge_the_full_paid_ledger():
    first = {'paidLookups': 6, 'searchLookups': 4, 'qualificationLookups': 2, 'holdoutPasses': 1}
    later = {'paidLookups': 10, 'searchLookups': 7, 'qualificationLookups': 3, 'holdoutPasses': 2}
    events = {}
    record_native(events, {4: (first, None, (1, 0)), 7: (later, None, (1, 1))}, 8)
    current = Counter()
    recovered = []
    for cap in range(4, 9):
        current.update(events.get(cap, {}))
        recovered.append((current['paidLookups'], current['holdoutPasses']))
    assert recovered == [(6, 1)] * 3 + [(10, 2)] * 2
    with pytest.raises(ValueError):
        record_native({}, {6: (later, None, (1, 1))}, 8)


def test_heldout_scores_follow_case_identity_across_different_seed_orders():
    vector = [0, 0, 0, 0]
    accumulate(vector, (2, 0), (1, 0))
    accumulate(vector, (0, 2), (1, 0))
    assert vector == [1, 0, 1, 0]
