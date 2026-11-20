"""Certify the GEPA 0.1.4 two-candidate parent draw from partial grades."""

from random import Random


def _relations(old, new):
    old_low, old_high = (0, 1) if old is None else (old, old)
    new_low, new_high = (0, 1) if new is None else (new, new)
    return tuple(relation for relation, possible in (
        (-1, old_low < new_high), (0, old_low <= new_high and new_low <= old_high), (1, old_high > new_low),
    ) if possible)


def _owner_counts(relations):
    first_tie_owner = next(iter({0, 1}))
    possible = {(int(relation == 1), int(relation == -1),
                 first_tie_owner if relation == 0 else int(relation < 0)) for relation in relations[0]}
    for choices in relations[1:]:
        possible = {(old + int(relation == 1), new + int(relation == -1), first)
                    for old, new, first in possible for relation in choices}
    return possible


def _certified_draw(relations, rng):
    size = len(relations)
    initial = rng.getstate()
    preview = Random()
    result = None
    for old_only, new_only, first in _owner_counts(relations):
        preview.setstate(initial)
        if not old_only or not new_only:
            # A pointwise winner owns all rows after pruning. On an all-row
            # tie GEPA prunes the first equal candidate in frontier order.
            owner = int(not old_only) if old_only or new_only else 1 - first
            preview.randrange(size)
        else:
            ties = size - old_only - new_only
            first_count = (old_only if first == 0 else new_only) + ties
            offset = preview.randrange(size + ties)
            owner = first if offset < first_count else 1 - first
        draw = owner, preview.getstate()
        if result is not None and draw != result:
            return None
        result = draw
    owner, advanced = result
    rng.setstate(advanced)
    return owner


def select_two_candidate_parent(pool, size, grades, rng):
    """Read only enough to fix both the native parent and its RNG advancement.

    This covers two distinct candidates with scalar scores between zero and
    one and a full, equally weighted instance frontier. The supplied grades
    provide peek(prompt, index) and read(prompt, index) in validation order.
    Larger panels use the caller's complete-score path to bound CPU work.
    """
    if len(pool) != 2 or pool[0] == pool[1] or not 1 <= size <= 32:
        return None
    old, new = pool
    relations = [_relations(grades.peek(old, case), grades.peek(new, case)) for case in range(size)]
    for case in range(size):
        for prompt in pool:
            if grades.peek(prompt, case) is not None:
                continue
            owner = _certified_draw(relations, rng)
            if owner is not None:
                return pool[owner]
            grades.read(prompt, case)
            relations[case] = _relations(grades.peek(old, case), grades.peek(new, case))
    owner = _certified_draw(relations, rng)
    if owner is None:
        raise ValueError('Reading a validation grade must expose it in the paid cache')
    return pool[owner]
