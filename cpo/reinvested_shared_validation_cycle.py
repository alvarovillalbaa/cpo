"""Use a certified shared shortlist to fund more validation rounds."""

from functools import partial

from .certified_shared_validation_cycle import _shortlist
from .shared_validation_cycle import strict_screen
from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run


HALVING_ROUNDS = (1, 2, 4)


def _screen(incumbent, candidates, rows, evaluate, cap, *, reinvest=True):
    if any(row.critical for row in rows):
        return strict_screen(incumbent, candidates, rows, evaluate, cap, expected=True)

    paid = quoted = measured = incumbent_passes = 0
    scores = {}
    active = candidates
    priority = {prompt: index for index, prompt in enumerate(candidates)}

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    for depth, row in enumerate(rows, 1):
        quote = len(active) + 1
        if not active or quote > cap - (paid if reinvest else quoted):
            break
        quoted += quote
        incumbent_passes += observe(incumbent, row)
        measured += 1
        cutoff = (len(active) + 1) // 2 if depth in HALVING_ROUNDS else len(active)
        if depth == len(rows):
            cutoff = 1
        active = _shortlist(active, scores, priority, cutoff, 0, partial(observe, row=row))

    if measured and active and scores[active[0]] > incumbent_passes:
        winner = active[0]
        return FinalistResult(winner, winner, paid), ((incumbent_passes, measured), (scores[winner], measured))
    return FinalistResult(incumbent, None, paid), None


def run_reinvested_shared_validation_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                           metric_limit, qualify, minimum_gain=1, seed=0):
    """Compare candidates on shared validation rows and qualify one finalist.

    Quote the full next round before any of its reads. Skip a challenger read
    only when it cannot change the exact ranked shortlist. Its saved slot can
    pay for a later round. Every surviving prompt has an actual grade for each
    measured case. A nominee must beat the incumbent on measured cases.
    Critical validation panels use strict two-sided validation.
    Deployment still requires the exact gain on disjoint qualification cases.
    """
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed,
                screen=_screen)
