"""Skip shared validation replies once the shortlist is certain."""

from bisect import insort
from functools import partial

from .shared_validation_cycle import SCHEDULES, strict_screen
from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run


def _shortlist(active, scores, priority, cutoff, threshold, observe):
    optimistic = sorted((-scores.get(prompt, 0) - 1, priority[prompt], prompt) for prompt in active)
    ranked = []
    for upper, index, prompt in optimistic:
        if -upper < threshold or (len(ranked) == cutoff and (upper, index) > ranked[-1][:2]):
            break
        score = scores.get(prompt, 0) + observe(prompt)
        if score >= threshold:
            scores[prompt] = score
            insort(ranked, (-score, index, prompt))
            if len(ranked) > cutoff:
                ranked.pop()
    return tuple(prompt for _, _, prompt in ranked)


def _screen(incumbent, candidates, rows, evaluate, cap, *, widths, margin):
    if any(row.critical for row in rows):
        return strict_screen(incumbent, candidates, rows, evaluate, cap, expected=True)
    schedule = tuple(zip(widths, rows))
    paid = charged = measured = incumbent_passes = 0
    scores = {}
    remaining = candidates
    priority = {prompt: index for index, prompt in enumerate(candidates)}

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    for depth, (width, row) in enumerate(schedule, 1):
        active = remaining[:width]
        charge = len(active) + 1
        # Keep the original whole-round funding decisions even when reads are saved.
        if not active or charge > cap - charged:
            break
        charged += charge
        incumbent_passes += observe(incumbent, row)
        measured += 1
        rounds_left = len(schedule) - depth
        cutoff = schedule[depth][0] if rounds_left else 1
        remaining = _shortlist(active, scores, priority, cutoff, incumbent_passes + margin - rounds_left,
                               partial(observe, row=row))

    if measured and remaining and scores[remaining[0]] >= incumbent_passes + margin:
        winner = remaining[0]
        return FinalistResult(winner, winner, paid), ((incumbent_passes, measured), (scores[winner], measured))
    return FinalistResult(incumbent, None, paid), None


def run_certified_shared_validation_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                           metric_limit, qualify, schedule='wide', validation_gain=0,
                                           minimum_gain=1, seed=0):
    """Preserve the shared validation nominee with fewer paid boolean replies.

    For stable grades, each funded round keeps the same ranked shortlist as
    ordinary shared validation. Only exact survivor grades carry into later
    rounds and independent qualification. Saved reads remain unspent.
    Critical validation panels use the original strict screen.
    """
    if schedule not in SCHEDULES:
        raise ValueError('Use the wide or deep validation schedule')
    if type(validation_gain) is not int or validation_gain < 0:
        raise ValueError('The required validation gain must be a nonnegative integer')
    search = partial(_screen, widths=SCHEDULES[schedule], margin=validation_gain)
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed, screen=search)
