"""Schedule the exact validation certificate using remaining family gains."""

from collections import Counter

from .anchored_validation import certify_validation_gain


def certify_family_ordered_validation_gain(rows, anchor_passes, evaluate, *, known=None):
    """Keep the exact rule and read tighter families first when it can help.

    With at most one possible net gain left, any further miss proves that
    strict improvement is impossible. Keep the original row order in that
    case. The certificate retains its priority for cached and critical rows.
    """
    rows = tuple(rows)
    retained = {} if known is None else known
    slack = Counter(row.family for row in rows if anchor_passes.get(row.id) is False)
    slack.subtract(row.family for row in rows if retained.get(row.id) is False)
    order = sorted(rows, key=lambda row: slack[row.family]) if slack.total() > 1 else rows
    return certify_validation_gain(order, anchor_passes, evaluate, known=known)
