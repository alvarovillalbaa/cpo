"""Limit a one-row search after a paid incumbent miss."""

from functools import partial

from .quoted_shared_validation_cycle import _schedule, _screen as quoted_screen
from .second_row_validation import screen as second_row_screen


def screen(incumbent, candidates, rows, evaluate, cap, *, opening_width, repair):
    """Search only the prefix of challengers after a first validation miss.

    After an incumbent pass, retain the full roster and optionally look for
    a repair on the second validation row. Use the original screen for
    critical cases and when the configured budget buys multiple rounds.
    The caller still qualifies any nominee on a separate panel.
    """
    if type(opening_width) is not int or opening_width < 1:
        raise ValueError('Opening width must be a positive integer')
    ordinary = (partial(second_row_screen, preserve_first=False) if repair
                else partial(quoted_screen, halve=True))
    if (len(candidates) <= opening_width or any(row.critical for row in rows)
            or len(_schedule(len(candidates), rows, cap, True)) != 1):
        return ordinary(incumbent, candidates, rows, evaluate, cap)

    first = rows[0]
    initial = evaluate(incumbent, first)

    def reuse_first(prompt, row):
        return initial if prompt == incumbent and row == first else evaluate(prompt, row)

    if initial.passed is not False:
        return ordinary(incumbent, candidates, rows, reuse_first, cap)

    return quoted_screen(incumbent, candidates[:opening_width], rows[:1], reuse_first, cap, halve=True)
