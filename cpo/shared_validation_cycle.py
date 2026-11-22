"""Nominate by successive halving on paid common validation cases."""

from collections import Counter
from functools import partial

from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run, _screen as strict_screen


SCHEDULES = {'wide': (8, 4, 2), 'deep': (4, 3, 2, 2, 2)}


def _screen(incumbent, candidates, rows, evaluate, cap, *, widths, margin):
    if any(row.critical for row in rows):
        return strict_screen(incumbent, candidates, rows, evaluate, cap, expected=True)
    schedule = tuple(zip(widths, rows))
    paid = measured = incumbent_passes = 0
    scores = Counter()
    remaining = tuple(candidates)
    priority = {prompt: index for index, prompt in enumerate(remaining)}

    def observe(prompt, row):
        nonlocal paid
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Shared validation requires exact boolean replies')
        paid += 1
        return grade

    for depth, (width, row) in enumerate(schedule, 1):
        active = remaining[:width]
        if not active or len(active) + 1 > cap - paid:
            break
        incumbent_passes += observe(incumbent, row)
        for prompt in active:
            scores[prompt] += observe(prompt, row)
        measured += 1
        eligible = (prompt for prompt in active
                    if scores[prompt] + len(schedule) - depth >= incumbent_passes + margin)
        remaining = tuple(sorted(eligible, key=lambda prompt: (-scores[prompt], priority[prompt])))

    if measured and remaining and scores[remaining[0]] >= incumbent_passes + margin:
        winner = remaining[0]
        return FinalistResult(winner, winner, paid), ((incumbent_passes, measured), (scores[winner], measured))
    return FinalistResult(incumbent, None, paid), None


def run_shared_validation_cycle(incumbent, candidates, validation, qualification_rows, evaluate, *,
                                 metric_limit, qualify, schedule='wide', validation_gain=0, minimum_gain=1, seed=0):
    """Compare a fixed pool on funded shared cases, then qualify one nominee.

    The wide schedule starts with eight challengers and measures at most
    three cases. The deep schedule starts with four challengers and measures
    up to five. Buy only complete rounds, including the incumbent's reply.
    The required validation gain is measured on the cases both prompts saw.
    If validation includes a critical case, use strict two-sided validation.
    An exact gain on the independent qualification panel determines deployment.
    """
    if schedule not in SCHEDULES:
        raise ValueError('Use the wide or deep validation schedule')
    if type(validation_gain) is not int or validation_gain < 0:
        raise ValueError('The required validation gain must be a nonnegative integer')
    search = partial(_screen, widths=SCHEDULES[schedule], margin=validation_gain)
    return _run(incumbent, candidates, validation, qualification_rows, evaluate,
                metric_limit=metric_limit, qualify=qualify, minimum_gain=minimum_gain, seed=seed, screen=search)
