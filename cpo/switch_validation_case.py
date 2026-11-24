"""Switch the shared validation case after several unsuccessful probes."""

from .quoted_shared_validation_cycle import _schedule, _screen as quoted_screen
from .single_finalist import FinalistResult


def screen(incumbent, candidates, rows, evaluate, cap, *, initial_probes, unopened_first):
    """Look for a repair on a second case after the opening fails repeatedly.

    Require the incumbent and an ordered prefix of challengers to fail the
    opening case before switching. If the incumbent passes the second case,
    spend the remaining probes on the unfinished opening search. Otherwise
    look for a strict gain on the second case. Independent qualification
    still determines deployment. Unfunded and critical panels use the
    original screen.
    """
    if type(initial_probes) is not int or initial_probes < 1:
        raise ValueError('Initial probe count must be a positive integer')
    if (len(rows) < 2 or len(candidates) <= initial_probes or cap < initial_probes + 3
            or any(row.critical for row in rows) or len(_schedule(len(candidates), rows, cap, True)) != 1):
        return quoted_screen(incumbent, candidates, rows, evaluate, cap, halve=True)

    paid = 0

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    def probe(roster, row):
        for prompt in roster[:cap - paid]:
            if observe(prompt, row):
                return FinalistResult(prompt, prompt, paid), ((0, 1), (1, 1))
        return None

    first, second = rows[:2]
    if observe(incumbent, first):
        return FinalistResult(incumbent, None, paid), None
    checked = candidates[:initial_probes]
    active = candidates[initial_probes:]
    found = probe(checked, first)
    if found is not None:
        return found
    if observe(incumbent, second):
        found = probe(active, first)
    else:
        reordered = (*active, *checked) if unopened_first else candidates
        found = probe(reordered, second)
    return found or (FinalistResult(incumbent, None, paid), None)
