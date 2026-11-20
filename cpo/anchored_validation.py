"""Certify a challenger against an already measured validation anchor."""

from collections import Counter


def certify_validation_gain(rows, anchor_passes, evaluate, *, known=None):
    """Stop once unread challenger replies cannot change the exact decision.

    The fixed panel needs a strict gain, no family losses, and every critical
    pass of the anchor preserved. Only unread challenger rows call evaluate.
    """
    rows = tuple(rows)
    ids = {row.id for row in rows}
    known = {} if known is None else known
    if not ids or len(ids) != len(rows) or ids != anchor_passes.keys() or known.keys() - ids:
        raise ValueError('The anchor and known replies must refer to the distinct validation rows')
    if any(type(passed) is not bool for passed in (*anchor_passes.values(), *known.values())):
        raise ValueError('Validation requires exact boolean outcomes')

    protected = {row.id for row in rows if row.critical and anchor_passes[row.id]}
    lower = Counter()
    upper = Counter()
    for row in rows:
        before = anchor_passes[row.id]
        lower[row.family] -= before
        upper[row.family] += not before
    total_low, total_high = lower.total(), upper.total()
    order = sorted(rows, key=lambda row: (row.id not in known, row.id not in protected))
    for row in order:
        if total_high <= 0 or min(upper.values()) < 0:
            return False
        if not protected and total_low > 0 and min(lower.values()) >= 0:
            return True
        passed = known[row.id] if row.id in known else evaluate(row)
        if type(passed) is not bool:
            raise ValueError('Validation requires exact boolean outcomes')
        if row.id in protected and not passed:
            return False
        protected.discard(row.id)
        lower[row.family] += passed
        upper[row.family] -= not passed
        total_low += passed
        total_high -= not passed
    return total_low > 0 and min(lower.values()) >= 0
