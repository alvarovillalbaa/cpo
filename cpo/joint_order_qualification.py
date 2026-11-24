"""Order a short qualification proof under a joint distribution of paired grades."""

from fractions import Fraction
from functools import lru_cache

from .expected_qualification import _pass_rate
from .paired_order_certificate_cycle import _finish_with_partner_evidence
from .paired_qualification import QualificationDecision


# A row is untouched, or known on one side with a favorable bit of 0 or 1.
_ACTIONS = ((0, 0), (0, 1), (1, 1), (2, 1), (3, 0), (4, 0))


def validation_context(counts):
    """Use the existing coarse validation pass-rate estimates."""
    return tuple(_pass_rate(*side) for side in counts)


def _after(groups, group, side, favorable):
    remaining = list(groups)
    remaining[group] -= 1
    if group == 0:
        remaining[1 + 2 * side + favorable] += 1
    return tuple(remaining)


@lru_cache(maxsize=256)
def _chances(weights):
    a, b, c, d = weights
    return (Fraction(c + d, a + b + c + d), Fraction(b + d, a + b + c + d),
            Fraction(b, a + b), Fraction(d, c + d), Fraction(c, a + c), Fraction(d, b + d))


@lru_cache(maxsize=80_000)
def _order(size, minimum, weights, groups, hits):
    low = hits - size
    high = low + 2 * groups[0] + sum(groups[1:])
    if low >= minimum or high < minimum:
        return Fraction(0), None
    options = []
    for (group, side), chance in zip(_ACTIONS, _chances(weights), strict=True):
        if not groups[group]:
            continue
        failure, _ = _order(size, minimum, weights, _after(groups, group, side, 0), hits)
        success, _ = _order(size, minimum, weights, _after(groups, group, side, 1), hits + 1)
        options.append((1 + (1 - chance) * failure + chance * success, side, group))
    cost, side, group = min(options)
    return cost, (group, side)


def finish_joint_order(incumbent, challenger, rows, read, history, counts, minimum, seed, *, priors):
    """Complete a paid incumbent prefix with a policy learned on separate grades.

    The four weights describe (incumbent failure, challenger pass) in binary
    order. Positive weights estimate cost only. A promotion still requires an
    exact score bound derived from the replies. Use the existing certifier
    outside the short, single-family, noncritical case.
    """
    size = len(rows)
    if not 1 <= size <= 8 or len({row.family for row in rows}) != 1 or any(row.critical for row in rows):
        return _finish_with_partner_evidence(incumbent, challenger, rows, read, history, counts, minimum, seed)
    weights = tuple(priors.get(validation_context(counts), priors[None]))
    if len(weights) != 4 or any(type(value) is not int or value <= 0 for value in weights):
        raise ValueError('The joint prior requires four positive integer weights')
    known = {event.row_id: 1 + int(not event.passed) for event in history}
    kinds = [known.get(row.id, 0) for row in rows]
    groups = tuple(kinds.count(group) for group in range(5))
    hits = groups[2]
    prompts = incumbent, challenger
    while True:
        _, action = _order(size, minimum, weights, groups, hits)
        if action is None:
            low = hits - size
            high = low + 2 * groups[0] + sum(groups[1:])
            promoted = low >= minimum
            return QualificationDecision('promoted' if promoted else 'rejected',
                                         challenger if promoted else incumbent, tuple(history), low, high)
        group, side = action
        index = kinds.index(group)
        grade = read(prompts[side], rows[index], 0)
        favorable = int(grade == bool(side))
        kinds[index] = 1 + 2 * side + favorable if group == 0 else -1
        groups = _after(groups, group, side, favorable)
        hits += favorable
