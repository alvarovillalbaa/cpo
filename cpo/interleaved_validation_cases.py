"""Share remaining probes across two failed incumbent validation cases."""

from itertools import chain, islice

from .quoted_shared_validation_cycle import _schedule, _screen as quoted_screen
from .single_finalist import FinalistResult


def screen(incumbent, candidates, rows, evaluate, cap, *, second_first):
    """Hedge the two-failure switch by checking both cases per unopened prompt.

    When the incumbent and two challengers fail the opening case, buy the
    incumbent's next reply. If that case also fails, alternate probes on the
    two cases in the original unopened roster order. If it passes, continue
    the opening search. Nominate at the first repair and leave deployment to
    independent qualification. Use the original quote for other geometries
    and critical panels.
    """
    if (len(rows) < 2 or len(candidates) < 3 or cap < 5 or any(row.critical for row in rows)
            or len(_schedule(len(candidates), rows, cap, True)) != 1):
        return quoted_screen(incumbent, candidates, rows, evaluate, cap, halve=True)

    paid = 0

    def read(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    def nominate(probes):
        for prompt, row in islice(probes, cap - paid):
            if read(prompt, row):
                return FinalistResult(prompt, prompt, paid), ((0, 1), (1, 1))
        return None

    first, second = rows[:2]
    if read(incumbent, first):
        return FinalistResult(incumbent, None, paid), None
    early = nominate((prompt, first) for prompt in candidates[:2])
    if early is not None:
        return early
    opening = ((prompt, first) for prompt in candidates[2:])
    if read(incumbent, second):
        probes = opening
    else:
        alternate = ((prompt, second) for prompt in candidates[2:])
        pairs = zip(alternate, opening) if second_first else zip(opening, alternate)
        probes = chain.from_iterable(pairs)
    return nominate(probes) or (FinalistResult(incumbent, None, paid), None)
