"""Certify small GEPA 0.1.4 parent pools without reading every grade."""

from itertools import product
from math import prod
from random import Random


MAX_FRONTIERS = 128


def _subsets(mask):
    subset = mask
    while subset:
        yield subset
        subset = (subset - 1) & mask


def _possible_fronts(row):
    unknown = sum(1 << index for index, score in enumerate(row) if score is None)
    unknown_fronts = tuple(_subsets(unknown))
    known_best = max((score for score in row if score is not None), default=None)
    if known_best is None:
        return unknown_fronts
    known = sum(1 << index for index, score in enumerate(row) if score == known_best)
    # At either endpoint, unread grades can only tie or move in one direction.
    if known_best == 0:
        return (known | unknown, *unknown_fronts)
    tied = (known, *(known | subset for subset in unknown_fronts))
    if known_best == 1:
        return tied
    return (*tied, *unknown_fronts)


def _minimal_covers(fronts):
    """Enumerate survivor sets that can result from deleting covered candidates."""
    active = 0
    for front in fronts:
        active |= front
    seen, pending = {active}, [active]
    while pending:
        active = pending.pop()
        mandatory = 0
        for front in fronts:
            remaining = active & front
            if remaining.bit_count() == 1:
                mandatory |= remaining
        removable = active ^ mandatory
        if not removable:
            yield active
        while removable:
            candidate = removable & -removable
            reduced = active ^ candidate
            if reduced not in seen:
                seen.add(reduced)
                pending.append(reduced)
            removable ^= candidate


def _sampling_list(fronts, survivors, width):
    counts = {}
    for front in fronts:
        winners = {index for index in range(width) if front & (1 << index)}
        for index in {index for index in winners if survivors & (1 << index)}:
            counts[index] = counts.get(index, 0) + 1
    return [index for index, count in counts.items() for _ in range(count)]


def _certify(options, width, rng):
    if prod(map(len, options)) > MAX_FRONTIERS:
        return None
    initial = rng.getstate()
    preview = Random(0)
    draws = {}
    result = None
    for fronts in product(*options):
        for survivors in _minimal_covers(fronts):
            population = _sampling_list(fronts, survivors, width)
            size = len(population)
            if size not in draws:
                preview.setstate(initial)
                draws[size] = preview.randrange(size), preview.getstate()
            offset, advanced = draws[size]
            draw = population[offset], advanced
            if result is not None and result != draw:
                return None
            result = draw
    index, advanced = result
    rng.setstate(advanced)
    return index


def select_frontier_parent(pool, size, grades, rng, *, prioritize_uncertain_cases=False):
    """Certify a seeded draw for 3–7 distinct candidates and 1–32 cases.

    Unknown grades can be any value from zero to one. The search overapproximates
    GEPA's possible pruning orders by considering every irreducible cover of the
    possible per-case winning sets. It accepts only when they all choose the
    same parent and leave the shared RNG in the same state. A None result asks
    the caller to finish using GEPA's complete-score calculation.

    With prioritize_uncertain_cases, check the cases with the most possible
    winner sets in the existing cache first. Ties keep validation order.
    """
    width = len(pool)
    if not 3 <= width <= 7 or len(set(pool)) != width or not 1 <= size <= 32:
        return None
    rows = [[grades.peek(prompt, case) for prompt in pool] for case in range(size)]
    options = [_possible_fronts(row) for row in rows]
    cases = range(size)
    if prioritize_uncertain_cases:
        cases = sorted(cases, key=lambda case: -len(options[case]))
    for case in cases:
        row = rows[case]
        for index, score in enumerate(row):
            if score is not None:
                continue
            owner = _certify(options, width, rng)
            if owner is not None:
                return pool[owner]
            row[index] = grades.read(pool[index], case)
            options[case] = _possible_fronts(row)
    return None
