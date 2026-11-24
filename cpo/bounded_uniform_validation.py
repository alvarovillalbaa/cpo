"""Use optimistic total-score bounds to settle uniform validation."""

from functools import partial
from heapq import heapify, heappop, heappush

from .perfect_challenger_screen import screen as perfect_screen
from .quoted_shared_validation_cycle import _schedule
from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run


def screen(incumbent, candidates, rows, evaluate, cap, *, halve):
    """Preserve the quoted decision while ordering uniform reads by bound."""
    if halve or any(row.critical for row in rows):
        return perfect_screen(incumbent, candidates, rows, evaluate, cap, halve=halve)

    funded = [row for row, _ in _schedule(len(candidates), rows, cap, False)]
    paid = 0

    def read(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    incumbent_score = sum(read(incumbent, row) for row in funded)
    width = len(funded)
    # A candidate's upper bound falls only on a failed read. The original
    # roster index settles ties at every step and in the final choice.
    pending = [(-width, index, 0) for index in range(len(candidates))]
    heapify(pending)
    while pending:
        negative_bound, index, seen = heappop(pending)
        if -negative_bound <= incumbent_score:
            break
        prompt = candidates[index]
        if seen == width:
            return (FinalistResult(prompt, prompt, paid),
                    ((incumbent_score, width), (-negative_bound, width)))
        grade = read(prompt, funded[seen])
        heappush(pending, (negative_bound + (not grade), index, seen + 1))
    return FinalistResult(incumbent, None, paid), None


def run_bounded_uniform_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                               metric_limit, qualify, schedule='uniform', minimum_gain=1, seed=0):
    """Settle the quoted validation winner with exact prefix bounds.

    Uniform validation reads the next case of the candidate with the best
    optimistic score. A complete score above the incumbent wins once every
    other upper bound ranks behind it. Successive halving uses the existing
    perfect-challenger optimization. Critical panels use the strict screen.
    Every nominee still needs independent qualification to deploy.
    """
    if schedule not in ('uniform', 'successive-halving'):
        raise ValueError('Use uniform or successive-halving validation')
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed,
                screen=partial(screen, halve=schedule == 'successive-halving'))
