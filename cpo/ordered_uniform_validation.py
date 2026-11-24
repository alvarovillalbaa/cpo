"""Use paid incumbent grades to order the funded uniform validation cases."""

from functools import partial

from .bounded_uniform_validation import screen as bounded_screen
from .quoted_shared_validation_cycle import _schedule
from .two_sided_certificate_cycle import _run


ORIGINAL, MISSES, PASSES = 'original', 'miss-first', 'pass-first'
ORDERS = (ORIGINAL, MISSES, PASSES)


def screen(incumbent, candidates, rows, evaluate, cap, *, order):
    """Change read order while preserving the uniform score and proof."""
    if order not in ORDERS:
        raise ValueError('Use a supported uniform validation order')
    if order == ORIGINAL or any(row.critical for row in rows):
        return bounded_screen(incumbent, candidates, rows, evaluate, cap, halve=False)

    funded = [row for row, _ in _schedule(len(candidates), rows, cap, False)]
    paid = {row.id: evaluate(incumbent, row) for row in funded}
    if any(type(reply.passed) is not bool for reply in paid.values()):
        raise ValueError('Shared validation requires exact boolean replies')
    reordered = sorted(funded, key=lambda row: paid[row.id].passed, reverse=order == PASSES)

    def reuse(prompt, row):
        return paid[row.id] if prompt == incumbent else evaluate(prompt, row)

    return bounded_screen(incumbent, candidates, reordered, reuse, cap, halve=False)


def run_ordered_uniform_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                               metric_limit, qualify, order=MISSES, minimum_gain=1, seed=0):
    """Order funded uniform cases by paid incumbent grades, then qualify.

    The quote fixes the case set before any reads. Case order changes only
    the order of challenger replies. The exact uniform winner, score and
    independent qualification depend on grades, with ties in roster order.
    Critical cases keep the strict validation path.
    """
    if order not in ORDERS:
        raise ValueError('Use a supported uniform validation order')
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed,
                screen=partial(screen, order=order))
