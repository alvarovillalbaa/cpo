"""Order fresh paired qualification replies by expected remaining proof work."""

from functools import lru_cache

from .paired_qualification import QualificationDecision, QualificationObservation, certify_paired_qualification


def _bounds(sizes, state):
    low = tuple(favorable - size for size, (_, _, favorable) in zip(sizes, state, strict=True))
    high = tuple(size + favorable - old - new
                 for size, (old, new, favorable) in zip(sizes, state, strict=True))
    return low, high


def _settled(low, high, minimum):
    if min(high) < 0 or sum(high) < minimum:
        return 'rejected'
    if min(low) >= 0 and sum(low) >= minimum:
        return 'promoted'
    return None


def _advance(state, family, side, favorable):
    old, new, hits = state[family]
    changed = (old + (side == 0), new + (side == 1), hits + favorable)
    return (*state[:family], changed, *state[family + 1:])


@lru_cache(maxsize=240_000)
def _minimum_expected_reads(sizes, rates, minimum, state):
    if _settled(*_bounds(sizes, state), minimum) is not None:
        return 0, None
    remaining = 2 * sum(sizes) - sum(old + new for old, new, _ in state)
    # Scale by 4**remaining so quarter probabilities and ties are exact.
    scale = 4**remaining
    best = None
    for family, size in enumerate(sizes):
        for side, likelihood in enumerate(rates):
            if state[family][side] == size:
                continue
            miss, _ = _minimum_expected_reads(sizes, rates, minimum, _advance(state, family, side, False))
            hit, _ = _minimum_expected_reads(sizes, rates, minimum, _advance(state, family, side, True))
            option = (scale + (4 - likelihood) * miss + likelihood * hit, (family, side))
            if best is None or option < best:
                best = option
    return best


def _pass_rate(passed, sampled):
    passed, sampled = passed + 1, sampled + 2
    return 1 if 8 * passed < 3 * sampled else 3 if 8 * passed > 5 * sampled else 2


def certify_expected_qualification(incumbent, challenger, rows, evaluate, *, validation_counts=((0, 0), (0, 0)),
                                   repeats=1, minimum_gain=1, seed=0, evaluation_limit=None):
    """Use paid validation pass counts to order the original exact promotion proof.

    Supply (passed, observed) for the incumbent and challenger, respectively.
    The estimates only order replies. Up to eight qualification rows in one
    or two families use expected-cost order. Critical rows, repeated replies,
    and larger or more varied panels use the original seeded certificate.
    """
    if (len(validation_counts) != 2 or any(len(pair) != 2 for pair in validation_counts)
            or any(type(passed) is not int or type(sampled) is not int or not 0 <= passed <= sampled
                   for passed, sampled in validation_counts)):
        raise ValueError('Validation counts require two (passed, observed) integer pairs')
    rows = tuple(rows)
    families = {}
    for row in rows:
        families.setdefault(row.family, []).append(row)
    if (not rows or len(rows) > 8 or len(families) > 2 or any(row.critical for row in rows)
            or type(repeats) is not int or repeats != 1
            or type(minimum_gain) is not int or minimum_gain < 1
            or (evaluation_limit is not None and (type(evaluation_limit) is not int or evaluation_limit < 0))
            or len({row.id for row in rows}) != len(rows) or incumbent == challenger):
        return certify_paired_qualification(incumbent, challenger, rows, evaluate, repeats=repeats,
                                            minimum_gain=minimum_gain, seed=seed, evaluation_limit=evaluation_limit)
    prompts = incumbent, challenger
    rates = (4 - _pass_rate(*validation_counts[0]), _pass_rate(*validation_counts[1]))
    groups = tuple(families.values())
    sizes = tuple(map(len, groups))
    state = ((0, 0, 0),) * len(sizes)
    observed = []
    while True:
        low, high = _bounds(sizes, state)
        status = _settled(low, high, minimum_gain)
        if status is None and len(observed) == evaluation_limit:
            status = 'undecided'
        if status is not None:
            return QualificationDecision(status, challenger if status == 'promoted' else incumbent,
                                         tuple(observed), sum(low), sum(high))
        _, (family, side) = _minimum_expected_reads(sizes, rates, minimum_gain, state)
        row = groups[family][state[family][side]]
        passed = evaluate(prompts[side], row, 0)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        observed.append(QualificationObservation(prompts[side], row.id, 0, passed))
        state = _advance(state, family, side, passed == bool(side))
