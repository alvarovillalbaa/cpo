"""Decide the opening promotion gate from partial paired validation."""

from collections import Counter


def certify_opening_validation(incumbent, challenger, rows, observations, observe, *, order_missing=None):
    """Reuse observations and settle the exact gate, checking critical rows first.

    An optional order_missing callback permutes the remaining queries.
    """
    sizes = Counter(row.family for row in rows)
    lower = Counter({family: -count for family, count in sizes.items()})
    upper = sizes.copy()
    unresolved_critical = set()
    prompts = (incumbent, challenger)

    def passed(prompt, row):
        reply = observations.get((prompt, row.id))
        return reply.passed if reply is not None else None

    def count(prompt, row, outcome):
        if outcome == (prompt == challenger):
            lower[row.family] += 1
        else:
            upper[row.family] -= 1

    def check_critical(row):
        old, new = (passed(prompt, row) for prompt in prompts)
        if old is True and new is False:
            return False
        if old is False or new is True:
            unresolved_critical.discard(row.id)
        else:
            unresolved_critical.add(row.id)
        return True

    def decision():
        if sum(upper.values()) < 1 or min(upper.values()) < 0:
            return False
        if not unresolved_critical and sum(lower.values()) >= 1 and min(lower.values()) >= 0:
            return True
        return None

    def unobserved():
        for row in rows:
            for prompt in prompts:
                if (prompt, row.id) not in observations:
                    yield prompt, row

    def remaining():
        for row in rows:
            for prompt in prompts:
                if row.id in unresolved_critical and (prompt, row.id) not in observations:
                    yield prompt, row
        pending = unobserved()
        yield from pending if order_missing is None else order_missing(pending)

    for row in rows:
        for prompt in prompts:
            outcome = passed(prompt, row)
            if outcome is not None:
                count(prompt, row, outcome)
        if row.critical and not check_critical(row):
            return False
    settled = decision()
    if settled is not None:
        return settled
    for prompt, row in remaining():
        count(prompt, row, observe(prompt, row).passed)
        if row.critical and not check_critical(row):
            return False
        settled = decision()
        if settled is not None:
            return settled
    raise AssertionError('Complete validation must settle the promotion gate')
