from functools import lru_cache
from itertools import product

import pytest

from cpo.halving import HalvingSearch
from cpo.halving.cached_lookahead import CachedLookaheadHalving
from cpo.halving.lookahead import LookaheadHalving


PROMPTS = tuple(str(index) for index in range(13))
CASES = (0, 1, 2, 3)
KEYS = tuple(product(PROMPTS[:4], CASES[:3]))


def test_cold_path_matches_every_four_prompt_board():
    round_reads, new_reads = 0, 0
    for bits in product((False, True), repeat=len(KEYS)):
        board = dict(zip(KEYS, bits, strict=True))
        paths = []
        for selector in (HalvingSearch, CachedLookaheadHalving):
            search = selector(metric_limit=8)
            requests = []

            def read(prompt, case):
                requests.append((prompt, case))
                return board[prompt, case]

            winner = search.select(PROMPTS, CASES, read)
            assert search.evaluations == len(requests) == len(search.observations)
            paths.append((winner, requests))
        (expected, baseline), (settled, new) = paths
        assert expected == settled
        assert baseline == new
        round_reads += len(baseline)
        new_reads += len(new)
    assert round_reads == new_reads == 24832


def test_round_order_is_optimal_when_no_cold_board_can_cost_more():
    # A board permits exactly the reads round order bought on that board.
    board_count = 1 << len(KEYS)
    pass_masks = [0] * len(KEYS)
    winner_masks = dict.fromkeys(PROMPTS[:4], 0)
    spent_masks = [0] * (len(KEYS) + 1)
    for board in range(board_count):
        flag = 1 << board
        grades = {key: bool(board & (1 << index)) for index, key in enumerate(KEYS)}
        search = HalvingSearch(metric_limit=8)
        winner = search.select(PROMPTS, CASES, lambda prompt, case: grades[prompt, case])
        winner_masks[winner] |= flag
        for index, passed in enumerate(grades.values()):
            if passed:
                pass_masks[index] |= flag
        for depth in range(search.evaluations, len(spent_masks)):
            spent_masks[depth] |= flag

    @lru_cache(maxsize=None)
    def optimal_work(boards):
        if any(boards & mask == boards for mask in winner_masks.values()):
            return 0
        count = boards.bit_count()
        depth = len(KEYS) - (count.bit_length() - 1)
        if boards & spent_masks[depth]:
            return None
        feasible = []
        for mask in pass_masks:
            passed, failed = boards & mask, boards & ~mask
            if passed and failed:
                costs = optimal_work(passed), optimal_work(failed)
                if None not in costs:
                    feasible.append(count + sum(costs))
        return min(feasible, default=None)

    assert optimal_work((1 << board_count) - 1) == 24832


def test_cached_board_preserves_exact_previous_lookahead_path():
    paid = {('0', 1): True, ('1', 0): True}
    selectors = (LookaheadHalving(metric_limit=5, paid=paid), CachedLookaheadHalving(metric_limit=5, paid=paid))
    choices = [search.select(PROMPTS, CASES, lambda p, c: c > int(p)) for search in selectors]
    assert choices[0] == choices[1]
    assert selectors[0].observations == selectors[1].observations
    assert selectors[0].evaluations == selectors[1].evaluations


def test_inactive_prompt_cache_keeps_cold_route_and_cap_applies_once():
    paid = {('12', 0): True}
    search = CachedLookaheadHalving(metric_limit=8, paid=paid)
    assert search.select(PROMPTS, CASES, lambda *_: False) == '0'
    assert search.evaluations == len(search.observations) - 1
    capped = CachedLookaheadHalving(metric_limit=search.evaluations - 1, paid=paid)
    assert capped.select(PROMPTS, CASES, lambda *_: False) is None
    assert capped.exhausted
    assert capped.select(PROMPTS, CASES, lambda *_: pytest.fail('budget exceeded')) is None


def test_invalid_response_and_inputs_have_original_validation():
    search = CachedLookaheadHalving(metric_limit=8)
    with pytest.raises(ValueError, match='boolean'):
        search.select(PROMPTS, CASES, lambda *_: 1)
    assert search.evaluations == 1 and search.observations == {}
    with pytest.raises(ValueError, match='distinct'):
        search.select((*PROMPTS[:3], PROMPTS[0]), CASES, lambda *_: pytest.fail('invalid roster evaluated'))
