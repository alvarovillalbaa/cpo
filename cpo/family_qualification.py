"""Schedule exact paired evidence by unresolved critical losses and family bounds."""

from collections import Counter
from fractions import Fraction

from .optimizer import balanced_order
from .paired_qualification import QualificationDecision, QualificationObservation


def certify_family_qualification(incumbent, challenger, rows, qualify, *, repeats=1, minimum_gain=1, seed=0,
                                 evaluation_limit=None):
    """Schedule calls by critical pairs and family bounds, with an exact paired decision.

    Forecasts based on prior replies affect ordering only. A promotion needs
    a guaranteed net gain, nonregression in every family, and no unresolved
    critical loss. A finite evaluation limit may leave the result undecided.
    """
    rows = tuple(rows)
    if not rows or len({row.id for row in rows}) != len(rows):
        raise ValueError('Qualification requires distinct nonempty rows')
    if any(type(value) is not int or value < 1 for value in (repeats, minimum_gain)):
        raise ValueError('Repeat and gain thresholds must be positive integers')
    if evaluation_limit is not None and (type(evaluation_limit) is not int or evaluation_limit < 0):
        raise ValueError('The evaluation limit must be a nonnegative integer')
    if incumbent == challenger:
        return QualificationDecision('rejected', incumbent, (), 0, 0)

    cases = {(row.id, repeat): row for row in balanced_order(rows, seed) for repeat in range(repeats)}
    sizes = Counter(row.family for row in cases.values())
    lower = {family: -count for family, count in sizes.items()}
    upper = dict(sizes)
    critical = dict.fromkeys(key for key, row in cases.items() if row.critical)
    pending = [dict(cases), dict(cases)]
    evidence, replies = {}, []
    favorable, counts = [0, 0], [0, 0]
    prompts = (incumbent, challenger)
    critical_loss = False

    while True:
        total_low, total_high = sum(lower.values()), sum(upper.values())
        if critical_loss or total_high < minimum_gain or min(upper.values()) < 0:
            return QualificationDecision('rejected', incumbent, tuple(replies), total_low, total_high)
        if not critical and total_low >= minimum_gain and min(lower.values()) >= 0:
            return QualificationDecision('promoted', challenger, tuple(replies), total_low, total_high)
        if evaluation_limit == len(replies):
            return QualificationDecision('undecided', incumbent, tuple(replies), total_low, total_high)

        chances = tuple(Fraction(hit + 1, count + 2) for hit, count in zip(favorable, counts, strict=True))
        if critical:
            key = next(iter(critical))
            side = max((side for side in (0, 1) if key in pending[side]), key=lambda i: (chances[i], i))
        else:
            family = min(lower, key=lower.get)
            preferred = {i: tuple(key for key, row in bank.items() if lower[family] >= 0 or row.family == family)
                         for i, bank in enumerate(pending)}
            side = max((side for side, keys in preferred.items() if keys), key=lambda i: (chances[i], i))
            key = preferred[side][0]
        row = pending[side].pop(key)
        passed = qualify(prompts[side], row, key[1])
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean replies')
        evidence[side, key] = passed
        replies.append(QualificationObservation(prompts[side], row.id, key[1], passed))
        counts[side] += 1
        if passed == bool(side):
            favorable[side] += 1
            lower[row.family] += 1
        else:
            upper[row.family] -= 1
        if key in critical:
            old, new = evidence.get((0, key)), evidence.get((1, key))
            critical_loss = old is True and new is False
            if old is False or new is True or critical_loss:
                del critical[key]
