"""Order exact uniform reads using a bounded model of the remaining replies."""

from functools import lru_cache, partial

from cpo.ordered_uniform_validation import MISSES, screen as ordered_screen
from cpo.quoted_shared_validation_cycle import _schedule
from cpo.single_finalist import FinalistResult


_ORIGINAL = partial(ordered_screen, order=MISSES)


def certain_winner(depth, state):
    base, first, second = state
    if base[0] >= depth - min(first[1], second[1]):
        return 0
    if first[0] > depth - base[1] and first[0] >= depth - second[1]:
        return 1
    if second[0] > max(depth - base[1], depth - first[1]):
        return 2
    return None


def advance(state, side, passed):
    passes, misses = state[side]
    return state[:side] + ((passes + passed, misses + (not passed)),) + state[side + 1:]


@lru_cache(maxsize=None)
def select_read(depth, state):
    winner = certain_winner(depth, state)
    if winner == 0:
        return 0, None
    if winner is not None:
        remaining_base = depth - sum(state[0])
        remaining_winner = depth - sum(state[winner])
        return remaining_base + remaining_winner, 0 if remaining_base else winner

    options = []
    for side, (passes, misses) in enumerate(state):
        if passes + misses == depth or (side and depth - misses <= state[0][0]):
            continue
        after_hit = select_read(depth, advance(state, side, True))[0]
        after_miss = select_read(depth, advance(state, side, False))[0]
        # Beta(1, 1) per prompt. These probabilities only order reads.
        expected = (after_hit * (passes + 1) + after_miss * (misses + 1)) / (passes + misses + 2)
        options.append((1 + expected, side))
    return min(options)


def screen(incumbent, candidates, rows, evaluate, cap):
    if len(candidates) != 2 or any(row.critical for row in rows):
        return _ORIGINAL(incumbent, candidates, rows, evaluate, cap)
    funded = [row for row, _ in _schedule(2, rows, cap, False)]
    depth = len(funded)
    if not 3 <= depth <= 6:
        return _ORIGINAL(incumbent, candidates, rows, evaluate, cap)

    prompts = (incumbent, *candidates)
    observed = ({}, {}, {})
    state = ((0, 0),) * 3
    for paid in range(depth * len(prompts) + 1):
        winner = certain_winner(depth, state)
        if winner == 0:
            return FinalistResult(incumbent, None, paid), None
        if winner is not None and sum(state[0]) == sum(state[winner]) == depth:
            nominee = prompts[winner]
            return FinalistResult(nominee, nominee, paid), ((state[0][0], depth), (state[winner][0], depth))
        _, side = select_read(depth, state)
        pending = [row for row in funded if row.id not in observed[side]]
        row = min(pending, key=lambda row: observed[0].get(row.id) is not False) if side else pending[0]
        grade = evaluate(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        observed[side][row.id] = grade
        state = advance(state, side, grade)
    raise RuntimeError('Uniform bounds must settle within the original quote')
