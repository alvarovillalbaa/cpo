from fractions import Fraction

from benchmarks import witness_admission_credit as credit


def test_forecast_prices_a_strict_gain_and_an_exact_tie_extension():
    half = Fraction(1, 2)

    assert credit.forecast(1, 0, 1, half, half) == Fraction(1, 4)
    assert credit.forecast(1, 1, 1, half, half) == Fraction(3, 8)
    assert credit.forecast(1, 1, 1, Fraction(0), Fraction(1)) == 1
    assert credit.forecast(1, 1, 2, Fraction(0), Fraction(1)) == 0


def test_queue_reserves_full_cap_and_refunds_unused_reads_before_next_dispatch():
    calls = []

    def item(index, predicted):
        def settle():
            calls.append(index)
            return credit.Settlement(5, (0,), False)

        return credit.Opportunity((0, index), 'task', Fraction(0), Fraction(predicted, 3), settle)

    queue = [item(0, 1), item(1, 3), item(2, 2)]
    receipts, leftover = credit.allocate(queue, credit.CERTIFICATE, credit.CAP + 5, lambda entry: entry.settle())

    assert tuple(receipts) == ((0, 1), (0, 2))
    assert calls == [1, 2]
    assert leftover == credit.CAP - 5


def test_other_family_fit_uses_promotions_then_spend_without_holdout():
    rows = {arm: {'holdoutPasses': 0} for arm in credit.METHODS}
    rows[credit.SCHEDULE].update(newPromotions=4, extraLookups=70)
    rows[credit.MARGIN].update(newPromotions=4, extraLookups=60)
    rows[credit.CERTIFICATE].update(newPromotions=3, extraLookups=40, holdoutPasses=1000)

    assert credit.select([{'totals': rows}]) == credit.MARGIN
