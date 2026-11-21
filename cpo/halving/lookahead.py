"""Choose paid grades for the exact winner of a small Halving schedule."""

from functools import lru_cache

from . import HalvingSearch


_DEPTH = 3
_MAX_COMPLETIONS = 1 << 9


def _winner(board, width):
    def total(prompt, depth):
        return ((board >> (_DEPTH * prompt)) & ((1 << depth) - 1)).bit_count()

    survivors = sorted(range(width), key=lambda prompt: -total(prompt, 1))[:2]
    return max(survivors, key=lambda prompt: total(prompt, _DEPTH))


@lru_cache(maxsize=2)
def _tables(width):
    cells = _DEPTH * width
    boards = range(1 << cells)
    all_boards = (1 << len(boards)) - 1
    passes = tuple(sum(1 << board for board in boards if board & (1 << cell)) for cell in range(cells))
    labels = tuple(_winner(board, width) for board in boards)
    winners = [0] * width
    for board, winner in enumerate(labels):
        winners[winner] |= 1 << board
    relevant = tuple(sum(1 << board for board in boards if labels[board] != labels[board ^ (1 << cell)])
                     for cell in range(cells))
    return all_boards, passes, tuple(winners), relevant


def _certain(possible, winners):
    for winner, mask in enumerate(winners):
        if possible & mask == possible:
            return winner
    return None


@lru_cache(maxsize=32768)
def _next(width, possible):
    """Minimize worst-case additional grades, then uniform total work at a tie."""
    _, masks, winners, relevant = _tables(width)
    winner = _certain(possible, winners)
    if winner is not None:
        return 0, 0, None, winner
    best = None
    for cell, mask in enumerate(masks):
        passed, failed = possible & mask, possible & ~mask
        # An unknown cell can help only if flipping it can change a feasible winner.
        if not passed or not failed or not possible & relevant[cell]:
            continue
        left, right = _next(width, failed), _next(width, passed)
        rank = 1 + max(left[0], right[0]), possible.bit_count() + left[1] + right[1], cell
        if best is None or rank < best:
            best = rank
    return (*best, None)


class LookaheadHalving(HalvingSearch):
    """Certify the final cap-eight winner after deterministic eliminations."""

    def select(self, candidates, validation, evaluate, *, logical_limit=8):
        prompts, cases = tuple(candidates), tuple(validation)
        if (type(logical_limit) is not int or logical_limit != 8 or len(prompts) < 3 or len(cases) < _DEPTH
                or any(not isinstance(prompt, str) for prompt in prompts)
                or len(set(prompts)) != len(prompts) or len(set(cases)) != len(cases)):
            return super().select(prompts, cases, evaluate, logical_limit=logical_limit)
        if self.exhausted:
            return None

        rounds = (len(prompts) - 1).bit_length()
        while rounds * len(prompts) > logical_limit:
            prompts = prompts[:(len(prompts) + 1) // 2]
            rounds -= 1
        width = len(prompts)
        keys = tuple((prompt, case) for prompt in prompts for case in cases[:_DEPTH])
        possible, masks, winners, _ = _tables(width)
        for key, mask in zip(keys, masks, strict=True):
            if key in self._paid:
                possible &= mask if self._paid[key] else ~mask

        while True:
            winner = _certain(possible, winners)
            if winner is not None:
                return prompts[winner]
            if not self._remaining:
                self.exhausted = True
                return None
            if possible.bit_count() > _MAX_COMPLETIONS:
                cell = next(index for index in range(0, len(keys), _DEPTH)
                            if (possible & masks[index]) not in (0, possible))
            else:
                _, _, cell, _ = _next(width, possible)
            key = keys[cell]
            self._remaining -= 1
            self.evaluations += 1
            grade = evaluate(*key)
            if type(grade) is not bool:
                raise ValueError('Halving requires exact boolean grades')
            self._paid[key] = grade
            mask = masks[cell]
            possible &= mask if grade else ~mask
