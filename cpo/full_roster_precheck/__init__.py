"""Opt-in qualification-precheck ordering for the full-roster feedback policy."""

from dataclasses import replace

from ..feedback_episode import FeedbackEpisodeResult, _FEEDBACK_RUNNERS, _FOLLOW_UP, _HALVING, _RETAIN
from ..fixed_pool_cycle import FixedPoolCycleResult
from ..settled_episode import EpisodeCycle, _ACTIONS, _MAX_VALIDATION_READS
from ..settled_episode_schedule import choose_schedule
from ..single_finalist import FinalistResult
from ..two_sided_certificate_cycle import _run


__all__ = ['run_full_roster_feedback_episode']

_WIDTHS = {_ACTIONS[1]: 8, _ACTIONS[2]: 4, _HALVING: 8}


def _cycle(schedule, incumbent, cycle, evaluate, qualify):
    runner = _FEEDBACK_RUNNERS[schedule]
    candidates, validation, qualification = cycle.candidates, cycle.validation, cycle.qualification
    options = {'metric_limit': _MAX_VALIDATION_READS, 'qualify': qualify, 'seed': cycle.seed}
    if (schedule not in _WIDTHS or len(candidates) < _WIDTHS[schedule]
            or any(row.critical for row in validation)):
        return runner(incumbent, candidates, validation, qualification, evaluate, **options)

    screen = runner.keywords['screen']
    selection, counts = screen(incumbent, candidates, validation, evaluate, _MAX_VALIDATION_READS)
    if selection.finalist is None:
        return FixedPoolCycleResult(selection, None)
    result = _run(incumbent, candidates, validation, qualification, evaluate, **options,
                  screen=lambda *_: (selection, counts))
    # The independent precheck can still close the gate. Keep every paid read.
    return replace(result, search=replace(result.search, evaluations=selection.evaluations))


def run_full_roster_feedback_episode(incumbent, training_rows, cycles, evaluate, *, probe, qualify):
    """Run feedback with validation before precheck on full quoted rosters.

    Inputs and callbacks match ``run_feedback_episode``. Each cycle has up to
    eight distinct challengers, 1–19 validation rows, and four qualification
    rows. The episode requires two training rows and globally distinct row IDs
    and candidate prompts. Replies must be stable for each prompt and row.

    Only an independently qualified finalist can deploy. A screened cycle
    without a nominee can have no qualification observations. Critical
    validation, undersized rosters, and the fitted opening precheck first.
    """
    training_rows = tuple(training_rows)
    prepared = tuple(EpisodeCycle(tuple(cycle.candidates), tuple(cycle.validation),
                                 tuple(cycle.qualification), cycle.seed) for cycle in cycles)
    if len(training_rows) != 2 or not prepared:
        raise ValueError('Supply two training rows and at least one cycle')

    row_ids = [row.id for row in training_rows]
    prompts = [incumbent]
    for cycle in prepared:
        if (len(cycle.candidates) > 8 or not 1 <= len(cycle.validation) <= _MAX_VALIDATION_READS
                or len(cycle.qualification) != 4):
            raise ValueError('Each cycle requires up to eight challengers, 1–19 validation rows and four qualification rows')
        prompts.extend(cycle.candidates)
        row_ids.extend(row.id for row in (*cycle.validation, *cycle.qualification))
    if len(set(row_ids)) != len(row_ids) or len(set(prompts)) != len(prompts):
        raise ValueError('The episode requires disjoint row IDs and distinct prompts')

    training_reads = 0

    def observe(prompt, row):
        nonlocal training_reads
        grade = probe(prompt, row)
        training_reads += 1
        return grade

    opening = choose_schedule(incumbent, training_rows, observe, actions=_ACTIONS)
    rejected = False
    results, schedules = [], []
    for cycle in prepared:
        schedule = _FOLLOW_UP[opening] if rejected else opening
        if schedule == _RETAIN:
            result = FixedPoolCycleResult(FinalistResult(incumbent, None, 0), None)
        else:
            result = _cycle(schedule, incumbent, cycle, evaluate, qualify)
        results.append(result)
        schedules.append(schedule)
        incumbent = result.prompt
        rejected = (result.search.finalist is not None and result.qualification is not None
                    and result.qualification.status == 'rejected')
    return FeedbackEpisodeResult(incumbent, opening, training_reads, tuple(results), tuple(schedules))
