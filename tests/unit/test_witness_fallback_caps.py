"""T2 checks for exact halving tie order and the physical fallback cap."""

from itertools import product

import pytest

from benchmarks import pool, witness_fallback_caps as study
from cpo.halving import HalvingSearch


def test_certified_halving_matches_every_small_board_and_respects_paid_keys():
    prompts, cases = ('start', 'a', 'b', 'c'), (0, 1, 2)
    keys = tuple(product(prompts, cases))
    for bits in product((False, True), repeat=len(keys)):
        scores = dict(zip(keys, bits, strict=True))
        plain_keys = set()

        def score(prompt, case):
            plain_keys.add((prompt, case))
            return scores[prompt, case]

        expected = pool.successive_halving(prompts, cases, score, 8)
        for cached in ((), keys[::2], keys[1::3]):
            original = {pair: scores[pair] for pair in cached}
            purchases = []

            def buy(prompt, case):
                purchases.append((prompt, case))
                return scores[prompt, case]

            selector = HalvingSearch(metric_limit=8, paid=original)
            assert selector.select(prompts, cases, buy) == expected
            assert not selector.exhausted
            assert len(set(purchases)) == len(purchases) == selector.evaluations
            assert not set(purchases) & original.keys()
            assert set(purchases) <= plain_keys


def test_paid_replies_can_finish_a_round_at_zero_new_lookup_budget():
    prompts, cases = ('incumbent', 'winner', 'last'), (0, 1, 2)
    preloaded = {(prompt, case): prompt == 'winner' for prompt, case in product(prompts, cases)}
    selector = HalvingSearch(metric_limit=0, paid=preloaded)

    def unavailable(*_):
        raise AssertionError('Cached selection tried to make a purchase')

    assert selector.select(prompts, cases, unavailable) == 'winner'
    assert not selector.exhausted and selector.evaluations == 0


def test_exhaustion_stops_future_cycles_before_any_extra_lookups():
    prompts, cases = ('incumbent', 'a', 'b'), (0, 1, 2)
    for search in (HalvingSearch, study.PlainHalving):
        purchased = []

        def observe(prompt, case):
            purchased.append((prompt, case))
            return False

        selector = search(metric_limit=1, paid={})
        for _ in range(2):
            assert selector.select(prompts, cases, observe) is None
        assert len(purchased) == selector.evaluations == 1 and selector.exhausted


def test_failed_evaluation_counts_against_the_cap():
    selector = HalvingSearch(metric_limit=1)
    with pytest.raises(ValueError, match='exact boolean'):
        selector.select(('start', 'candidate'), (0,), lambda *_: 1)
    assert selector.evaluations == 1 and selector.observations == {}

    def unavailable(*_):
        raise AssertionError('The invalid reply was already charged')

    assert selector.select(('start', 'candidate'), (0,), unavailable) is None
