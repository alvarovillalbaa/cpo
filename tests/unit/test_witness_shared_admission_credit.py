import pytest

from benchmarks import witness_shared_admission_credit as shared


def offer(index, kind, reserve, paid):
    return shared.Offer((0, index), 'task', kind, reserve, lambda: shared.credit.Settlement(paid, (0,), False))


def test_queue_skips_an_unaffordable_direct_proof_and_funds_a_retry_after_refund():
    candidates = [offer(0, shared.DIRECT, 24, 10), offer(1, shared.RETRY, 15, 6), offer(2, shared.RETRY, 14, 7)]
    calls = []

    def settle(item):
        calls.append(item.key)
        return item.settle()

    receipts, left = shared.allocate(candidates, shared.DIRECT_FIRST, 20, settle)

    assert list(receipts) == calls == [(0, 1), (0, 2)]
    assert left == 7


def test_queue_priority_changes_which_type_spends_the_same_credit():
    candidates = [offer(0, shared.DIRECT, 24, 18), offer(1, shared.RETRY, 14, 10)]

    direct, _ = shared.allocate(candidates, shared.DIRECT_FIRST, 24, lambda item: item.settle())
    retry, _ = shared.allocate(candidates, shared.RETRY_FIRST, 24, lambda item: item.settle())

    assert list(direct) == [(0, 0)]
    assert list(retry) == [(0, 1)]


def test_optional_proof_must_settle_within_its_reservation():
    with pytest.raises(ValueError, match='reservation'):
        shared.allocate([offer(0, shared.RETRY, 12, 13)], shared.RETRY_ONLY, 24, lambda item: item.settle())
