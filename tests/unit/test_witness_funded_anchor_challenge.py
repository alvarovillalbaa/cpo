from fractions import Fraction
from itertools import product

from benchmarks import witness_funded_anchor_challenge as replay


def test_only_already_paid_feasible_rivals_are_ranked():
    anchors = (1, 2, 3, 4)
    paid = {('nominee', 1): False, ('nominee', 2): False, ('cheap', 1): True, ('cheap', 2): True,
            ('rate', 1): True, **{('cheap', i): False for i in range(5, 10)},
            **{('rate', i): True for i in range(5, 10)}}
    winners, _ = replay.order_rivals('nominee', ('cheap', 'rate', 'unpaid'), anchors, paid)

    assert winners == {replay.CHEAPEST: 'cheap', replay.RATE: 'rate'}


def test_known_strict_gain_needs_no_new_callback():
    anchors = (1, 2, 3, 4)
    paid = {('nominee', 1): False, ('nominee', 2): False, ('rival', 1): True, ('rival', 2): True, ('rival', 3): True}

    def unexpected(*_):
        raise AssertionError('A completed certificate has no new reads')

    result = replay.challenge('nominee', 'rival', anchors, paid, {'nominee': Fraction(1, 4), 'rival': Fraction(4, 5)},
                              unexpected, 0)
    assert result == (True, 0, paid, True)


def test_challenge_only_switches_on_an_exact_gain_and_never_overspends():
    anchors = (1, 2)
    keys = tuple(product(('nominee', 'rival'), anchors))
    rates = dict.fromkeys(('nominee', 'rival'), Fraction(1, 2))
    for values in product((True, False), repeat=4):
        actual = dict(zip(keys, values, strict=True))
        for mask in product((True, False), repeat=4):
            paid = {key: actual[key] for key, seen in zip(keys, mask, strict=True) if seen}
            for cap in range(5):
                won, reads, ledger, _ = replay.challenge('nominee', 'rival', anchors, paid, rates,
                                                         lambda prompt, case: actual[prompt, case], cap)
                assert paid.items() <= ledger.items() <= actual.items()
                assert reads == len(ledger) - len(paid) <= cap
                low, _ = replay.bounds('nominee', 'rival', anchors, ledger)
                assert won == (low > 0)
