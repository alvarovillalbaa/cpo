import pytest

from benchmarks import witness_short_admission_credit as short


def test_tail_uses_the_remaining_balance_and_skips_below_the_certificate_minimum():
    caps = []

    def evaluate(cap):
        caps.append(cap)
        return short.credit.Settlement(cap, (0,), False)

    offers = [short.ProofOffer((0, i), 'subject', short.shared.DIRECT, 24, 16, 9, evaluate) for i in range(2)]
    result, left = short.allocate(offers, short.TAIL_CAP, 12, lambda offer: offer.settle())

    assert list(result) == [(0, 0)]
    assert left == 0 and caps == [12]
    assert short.allocate(offers, short.TAIL_CAP, 8, lambda offer: offer.settle()) == ({}, 8)


def test_base_cap_reserves_the_whole_base_before_callback_and_refunds_actual_spend():
    caps = []

    def evaluate(cap):
        caps.append(cap)
        return short.credit.Settlement(8, (0,), False)

    offers = [short.ProofOffer((0, i), 'subject', short.shared.DIRECT, 24, 16, 9, evaluate) for i in range(3)]
    result, left = short.allocate(offers, short.BASE_CAP, 24, lambda offer: offer.settle())

    assert list(result) == [(0, 0), (0, 1)]
    assert left == 8 and caps == [16, 16]


def test_shortened_settlement_cannot_exceed_the_quote():
    offer = short.ProofOffer((0, 0), 'subject', short.shared.RETRY, 15, 16, 9,
                             lambda cap: short.credit.Settlement(cap + 1, (0,), False))

    with pytest.raises(ValueError, match='shortened reservation'):
        short.allocate([offer], short.TAIL_CAP, 12, lambda item: item.settle())
