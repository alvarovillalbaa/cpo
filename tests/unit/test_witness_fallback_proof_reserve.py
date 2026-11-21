"""T2 checks for independent proof protection and dynamic search credit."""

from types import SimpleNamespace

import pytest

from benchmarks import witness_fallback_proof_reserve as study
from benchmarks import witness_fallback_reserve as original


def test_remaining_credit_sets_the_next_cap_with_full_proof_reserved():
    items = [SimpleNamespace(key=name, cost=cost) for name, cost in [('a', 15), ('b', 5), ('c', 24), ('d', 0)]]
    calls = []

    def settle(item, cap):
        calls.append((item.key, cap))
        return item.cost, (1,)

    rows, left = study.fund(items, issued=44, proof_reserve=24, max_search=16, settle=settle)
    assert calls == [('a', 16), ('b', 5), ('c', 0)]
    assert sum(row[2] for row in rows) == 44 and left == 0


def test_no_proof_credit_means_no_search_dispatch():
    def forbidden(*_):
        pytest.fail('Search started with incomplete independent proof credit')

    assert study.fund([SimpleNamespace(key='a')], 23, 24, 16, forbidden) == ([], 23)


def test_a_funded_receipt_cannot_exceed_the_authorized_search_and_proof():
    invoked = []

    def settle(item, cap):
        invoked.append(cap)
        return 30, ()

    with pytest.raises(ValueError, match='exceeded its funded search'):
        study.fund([SimpleNamespace(key=name) for name in ('a', 'b')], 29, 24, 16, settle)
    assert invoked == [5]


def test_complete_quotes_preserve_the_original_reservation_path():
    items = [SimpleNamespace(key=name, cost=cost) for name, cost in [('a', 20), ('b', 18), ('c', 0)]]
    reference, old_left = original.fund(items, 60, 40, lambda item: (item.cost, ()))
    actual, new_left = study.fund(items, 60, 24, 16, lambda item, cap: (item.cost, ()))
    assert [(key, paid, votes) for key, _, paid, votes in actual] == reference
    assert new_left == old_left == 22
