"""Find a perfect challenger without reading irrelevant later candidates."""

from functools import partial

from .quoted_shared_validation_cycle import _schedule, _screen as quoted_screen
from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run


def screen(incumbent, candidates, rows, evaluate, cap, *, halve):
    """Preserve every original funded round and shortlist cut."""
    if any(row.critical for row in rows):
        return quoted_screen(incumbent, candidates, rows, evaluate, cap, halve=halve)

    rounds = _schedule(len(candidates), rows, cap, halve)
    cache = {row.id: evaluate(incumbent, row) for row, _ in rounds}
    if any(type(reply.passed) is not bool for reply in cache.values()):
        raise ValueError('Shared validation requires exact boolean replies')
    size = len(rounds)
    incumbent_passes = sum(reply.passed for reply in cache.values())
    if incumbent_passes != size - 1:
        def reuse(prompt, row):
            return cache[row.id] if prompt == incumbent else evaluate(prompt, row)

        return quoted_screen(incumbent, candidates, rows, reuse, cap, halve=halve)

    # A single failure rules out a challenger. Perfect prefixes at a depth
    # tie, so earlier surviving candidates occupy that round's seats.
    cutoffs = [width for _, width in rounds[:-1]] + [1]
    filled = [0] * size
    paid = size
    for prompt in candidates:
        for index, (row, _) in enumerate(rounds):
            if filled[index] >= cutoffs[index]:
                break
            grade = evaluate(prompt, row).passed
            if type(grade) is not bool:
                raise ValueError('Shared validation requires exact boolean replies')
            paid += 1
            if not grade:
                break
            filled[index] += 1
        else:
            return FinalistResult(prompt, prompt, paid), ((incumbent_passes, size), (size, size))
    return FinalistResult(incumbent, None, paid), None


def run_perfect_challenger_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                  metric_limit, qualify, schedule='uniform', minimum_gain=1, seed=0):
    """Use candidate order when a perfect score is required, then qualify.

    Stable Boolean grades give the same nomination and qualification as the
    quoted uniform or successive-halving cycle. Candidate-major evaluation
    skips later candidates as soon as an eligible perfect score is certain.
    Critical validation and other scores use the original quoted screen.
    """
    if schedule not in ('uniform', 'successive-halving'):
        raise ValueError('Use uniform or successive-halving validation')
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed,
                screen=partial(screen, halve=schedule == 'successive-halving'))
