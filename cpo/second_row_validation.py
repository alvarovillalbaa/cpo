"""Use saved reads from a one-row screen to look for a later repair."""

from dataclasses import replace

from .quoted_shared_validation_cycle import _schedule, _screen as quoted_screen
from .shared_validation_cycle import strict_screen


def screen(incumbent, candidates, rows, evaluate, cap, *, preserve_first):
    """Open a second row only when the funded first row passed.

    The nominal cap and the first-row decision stay fixed. On a second-row
    miss, both variants admit the same ordered roster, with capacity reserved
    for one preservation grade. The guarded variant certifies a strict gain
    across the two rows. The other variant screens on the second row alone.
    The caller must independently qualify any nominee.
    """
    if (len(rows) < 2 or cap < 4 or any(row.critical for row in rows)
            or len(_schedule(len(candidates), rows, cap, True)) != 1):
        return quoted_screen(incumbent, candidates, rows, evaluate, cap, halve=True)

    first = rows[0]
    initial = evaluate(incumbent, first)

    def reuse_first(prompt, row):
        return initial if prompt == incumbent and row == first else evaluate(prompt, row)

    if initial.passed is not True:
        return quoted_screen(incumbent, candidates, rows, reuse_first, cap, halve=True)

    roster = candidates[:cap - 3]
    if preserve_first:
        return strict_screen(incumbent, roster, rows[:2], reuse_first, cap, expected=False)

    selection, counts = quoted_screen(incumbent, roster, rows[1:2], evaluate, cap - 1, halve=True)
    return replace(selection, evaluations=selection.evaluations + 1), counts
