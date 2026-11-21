import pytest

from benchmarks import witness_adaptive_admission_credit as adaptive


def offer(index, kind, reserve, paid, promoted, change=0):
    return adaptive.shared.Offer((0, index), 'subject', kind, reserve,
                                 lambda: adaptive.shared.credit.Settlement(paid, (change,), promoted))


def test_adaptive_order_prefers_a_settled_promotion_even_if_holdout_was_worse():
    direct, retry = adaptive.shared.DIRECT, adaptive.shared.RETRY
    queue = [offer(0, direct, 24, 15, False), offer(1, retry, 12, 8, True, -4),
             offer(2, direct, 24, 17, True, 20), offer(3, retry, 12, 7, False)]

    adaptive_order, left = adaptive.allocate(queue, adaptive.ADAPTIVE, 60, lambda item: item.settle())
    alternating, _ = adaptive.allocate(queue, adaptive.BALANCED, 60, lambda item: item.settle())

    assert list(adaptive_order) == [(0, 0), (0, 1), (0, 3), (0, 2)]
    assert list(alternating) == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert left == 13


def test_adaptive_can_skip_unaffordable_head_and_use_smaller_proof():
    direct, retry = adaptive.shared.DIRECT, adaptive.shared.RETRY
    queue = [offer(0, direct, 24, 6, False), offer(1, retry, 20, 8, False), offer(2, retry, 14, 7, False)]

    funded, left = adaptive.allocate(queue, adaptive.ADAPTIVE, 15, lambda item: item.settle())

    assert list(funded) == [(0, 2)]
    assert left == 8


def test_adaptive_rejects_settlement_above_the_reservation():
    excessive = offer(0, adaptive.shared.RETRY, 14, 15, False)

    with pytest.raises(ValueError, match='reserved lookups'):
        adaptive.allocate([excessive], adaptive.ADAPTIVE, 24, lambda item: item.settle())
