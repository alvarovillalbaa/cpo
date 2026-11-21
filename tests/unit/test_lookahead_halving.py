from itertools import product

import pytest

from cpo.halving import HalvingSearch
from cpo.halving.lookahead import LookaheadHalving, _next, _tables


PROMPTS = ('incumbent', 'rewrite', 'repair')
CASES = (0, 1, 2, 3)
RELEVANT = tuple(product(PROMPTS, CASES[:3]))


def test_all_three_prompt_boards_and_reused_grades():
    worst, previous = 0, 0
    round_reads, lookahead_reads = 0, 0
    for bits in product((False, True), repeat=len(RELEVANT)):
        board = dict(zip(RELEVANT, bits, strict=True))
        control = HalvingSearch(metric_limit=9)
        winner = control.select(PROMPTS, CASES, lambda p, c: board[p, c])
        previous = max(previous, control.evaluations)
        round_reads += control.evaluations
        for cache in ((), RELEVANT[:3], RELEVANT[1::3], RELEVANT):
            paid = {key: board[key] for key in cache}
            lookahead = LookaheadHalving(metric_limit=9, paid=paid)

            def evaluate(prompt, case):
                assert (prompt, case) not in paid
                return board[prompt, case]

            assert lookahead.select(PROMPTS, CASES, evaluate) == winner
            assert len(lookahead.observations) == len(paid) + lookahead.evaluations
            if not paid:
                worst = max(worst, lookahead.evaluations)
                lookahead_reads += lookahead.evaluations
    assert worst == _next(3, _tables(3)[0])[0] <= previous
    assert (round_reads, lookahead_reads) == (2768, 2704)


def test_all_four_prompt_boards_after_free_eliminations():
    prompts = (*PROMPTS, 'extra', *(str(index) for index in range(9)))
    relevant = tuple(product(prompts[:4], CASES[:3]))
    for bits in product((False, True), repeat=len(relevant)):
        board = dict(zip(relevant, bits, strict=True))
        evaluate = lambda prompt, case: board[prompt, case]
        current = HalvingSearch(metric_limit=8)
        whole = LookaheadHalving(metric_limit=8)
        assert whole.select(prompts, CASES, evaluate) == current.select(prompts, CASES, evaluate)
        assert not whole.exhausted


def test_paid_grades_and_cap_span_the_whole_episode():
    board = dict.fromkeys(RELEVANT, False)
    first = LookaheadHalving(metric_limit=9)
    assert first.select(PROMPTS, CASES, lambda p, c: board[p, c]) == 'incumbent'
    spent = first.evaluations
    assert first.select(PROMPTS, CASES, lambda *_: pytest.fail('cache miss')) == 'incumbent'
    assert first.evaluations == spent
    capped = LookaheadHalving(metric_limit=spent - 1)
    assert capped.select(PROMPTS, CASES, lambda p, c: board[p, c]) is None
    assert capped.evaluations == spent - 1 and capped.exhausted
    assert capped.select(PROMPTS, CASES, lambda *_: pytest.fail('budget exceeded')) is None


def test_other_shapes_use_the_original_selector():
    prompts, cases = PROMPTS[:2], CASES
    one, two = LookaheadHalving(metric_limit=9), HalvingSearch(metric_limit=9)
    grade = lambda p, c: (p, c) != ('incumbent', 0)
    assert one.select(prompts, cases, grade) == two.select(prompts, cases, grade)
    assert one.observations == two.observations
