from collections import Counter

import pytest

from benchmarks.witness_peer_case_order import orders, record, reordered_proof


def test_peer_estimates_ignore_duplicate_paid_pairs_and_guard_holdout():
    history, seen = {}, set()
    record(history, seen, {('a', 4): True, ('b', 4): False}, {9})
    record(history, seen, {('a', 4): True, ('c', 4): True}, {9})

    assert history == {4: Counter(passes=2, reads=3)}
    with pytest.raises(ValueError, match='holdout'):
        record(history, seen, {('a', 9): True}, {9})


def test_difficulty_prior_reorders_sides_in_opposite_directions():
    rows = [10, 20, 30]
    history = {10: Counter(passes=3, reads=3), 30: Counter(passes=0, reads=3)}

    assert orders(rows, {}, False) == ((10, 20, 30), (10, 20, 30))
    assert orders(rows, history, False) == ((30, 20, 10), (10, 20, 30))
    assert orders(rows, history, True) == ((10, 30, 20), (20, 30, 10))


@pytest.mark.parametrize('rotate', [False, True])
def test_reordered_proof_keeps_the_physical_cases_and_exact_gain(rotate):
    rows, calls = [10, 20, 30], []
    history = {10: Counter(passes=3, reads=3), 30: Counter(passes=0, reads=3)}
    evidence = {'old': {10: False, 20: True, 30: False}, 'rival': {10: False, 20: True, 30: True}}

    def grade(prompt, case):
        calls.append((prompt, case))
        return evidence[prompt][case]

    proof = reordered_proof('old', 'rival', rows, [], grade, {}, 1, 6, history, rotate)

    assert proof.prompt == 'rival'
    assert len(set(calls)) == len(calls) == len(proof.observations) <= 6
    for side, ordered in zip(('old', 'rival'), orders(rows, history, rotate), strict=True):
        read = tuple(row for prompt, row in calls if prompt == side)
        assert read == ordered[:len(read)]
