from itertools import product

import pytest

from benchmarks.witness_proof_split import bounded_first, split_proof


def test_futility_preserves_every_first_promotion_on_two_rows():
    for replies in product((False, True), repeat=4):
        board = dict(zip(product(('start', 'first'), range(2)), replies, strict=True))

        def grade(prompt, case):
            return board[prompt, case]

        fixed = bounded_first('start', 'first', [0, 1], [], grade, {}, 1, 3, False)
        early = bounded_first('start', 'first', [0, 1], [], grade, {}, 1, 3, True)
        assert early.lookups <= fixed.lookups
        assert early.prompt == fixed.prompt
        if fixed.status == 'promoted':
            assert early == fixed


def test_budget_futility_returns_credit_to_the_disjoint_rival():
    calls = []

    def grade(prompt, case):
        calls.append((prompt, case))
        return prompt != 'first' if case < 2 else prompt == 'second'

    decision = split_proof('start', 'first', 'second', [0, 1], [], [2, 3], [], grade, {}, 1, 6, True)

    assert decision.prompt == 'second'
    assert decision.retry is True
    assert decision.lookups == len(calls) == 4
    assert decision.retry_lookups == 3
    assert {case for _, case in calls[1:]} == {2, 3}


def test_disallows_overlapping_proof_reserves_and_funded_tie_extension():
    def unexpected(_prompt, _case):
        pytest.fail('Invalid allocation consumed a lookup')

    with pytest.raises(ValueError, match='disjoint'):
        split_proof('start', 'first', 'second', [0, 1], [2], [2, 3], [], unexpected, {}, 1, 6, False)
    with pytest.raises(ValueError, match='base tie'):
        bounded_first('start', 'first', [0, 1], [2], unexpected, {}, 1, 4, True)
