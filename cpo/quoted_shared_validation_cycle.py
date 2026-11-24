"""Skip replies that cannot change a fixed shared-row search decision."""

from functools import partial

from .certified_shared_validation_cycle import _shortlist
from .reinvested_shared_validation_cycle import HALVING_ROUNDS
from .shared_validation_cycle import strict_screen
from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run


def _schedule(width, rows, cap, halve):
    rounds = []
    for depth, row in enumerate(rows, 1):
        quote = width + 1
        if not width or quote > cap:
            break
        cap -= quote
        if halve and depth in HALVING_ROUNDS:
            width = (width + 1) // 2
        rounds.append((row, width))
    return rounds


def _screen(incumbent, candidates, rows, evaluate, cap, *, halve):
    if any(row.critical for row in rows):
        return strict_screen(incumbent, candidates, rows, evaluate, cap, expected=True)

    rounds = _schedule(len(candidates), rows, cap, halve)
    paid = 0

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    incumbent_passes = sum(observe(incumbent, row) for row, _ in rounds)
    size = len(rounds)
    if incumbent_passes == size:
        return FinalistResult(incumbent, None, paid), None

    active = candidates
    scores = {}
    priority = {prompt: index for index, prompt in enumerate(candidates)}
    for depth, (row, width) in enumerate(rounds, 1):
        threshold = incumbent_passes + 1 - (size - depth)
        cutoff = width if depth < size else 1
        active = _shortlist(active, scores, priority, cutoff, threshold, partial(observe, row=row))
        if not active:
            return FinalistResult(incumbent, None, paid), None

    winner = active[0]
    return FinalistResult(winner, winner, paid), ((incumbent_passes, size), (scores[winner], size))


def run_quoted_shared_validation_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                       metric_limit, qualify, schedule='uniform', minimum_gain=1, seed=0):
    """Run fixed uniform or successive-halving validation followed by exact proof.

    On noncritical panels, keep the eager schedule's original funded rows and
    roster cuts. Read the incumbent on those rows first. Skip candidates once
    they cannot beat the incumbent or reach the ranked shortlist. With stable
    boolean grades, the eager schedule's nominee and qualification are exact.
    Critical validation uses strict two-sided screening.
    """
    if schedule not in ('uniform', 'successive-halving'):
        raise ValueError('Use uniform or successive-halving validation')
    screen = partial(_screen, halve=schedule == 'successive-halving')
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed, screen=screen)
