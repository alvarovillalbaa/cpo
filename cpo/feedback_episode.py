"""Run the settled episode with a schedule switch after failed qualification."""

from dataclasses import dataclass
from functools import partial

from .bounded_uniform_validation import screen as bounded_screen
from .fixed_pool_cycle import FixedPoolCycleResult
from .settled_episode import EpisodeCycle, EpisodeResult, _ACTIONS, _limit, _MAX_VALIDATION_READS, _RUNNERS
from .settled_episode_schedule import choose_schedule
from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run


@dataclass(frozen=True)
class FeedbackEpisodeResult(EpisodeResult):
    cycle_schedules: tuple[str, ...]


_HALVING = 'successive-halving/8/14'
_RETAIN = 'retain-start'
_FOLLOW_UP = dict(zip(_ACTIONS, (_HALVING, _ACTIONS[0], _RETAIN), strict=True))
_FEEDBACK_RUNNERS = {
    **_RUNNERS,
    _HALVING: partial(_run, screen=partial(_limit, partial(bounded_screen, halve=True), 8, 14)),
}


def run_feedback_episode(incumbent, training_rows, cycles, evaluate, *, probe, qualify):
    """Run the frozen feedback policy for one or more prepared cycles.

    Use two training rows, up to eight challengers and one to nineteen
    validation rows per cycle, and four separate qualification rows per
    cycle. Prompts and row IDs are distinct throughout the episode. Probe
    and qualification callbacks return booleans. Validation returns an
    Observation. Grades stay stable within each cycle.

    A rejected finalist switches the very next cycle to its follow-up
    schedule. A skipped cycle retains the incumbent and buys no replies.
    The result records the opening schedule, each cycle's actual schedule
    and decision, and the total callbacks across the three roles.
    """
    training_rows, cycles = tuple(training_rows), tuple(cycles)
    if len(training_rows) != 2 or not cycles:
        raise ValueError('Supply two training rows and at least one cycle')

    row_ids = [row.id for row in training_rows]
    prompts = [incumbent]
    prepared = []
    for cycle in cycles:
        candidates = tuple(cycle.candidates)
        validation = tuple(cycle.validation)
        qualification = tuple(cycle.qualification)
        if (len(candidates) > 8 or not 1 <= len(validation) <= _MAX_VALIDATION_READS
                or len(qualification) != 4):
            raise ValueError('Each cycle requires up to eight challengers, 1–19 validation rows and four qualification rows')
        prompts.extend(candidates)
        row_ids.extend(row.id for row in (*validation, *qualification))
        prepared.append(EpisodeCycle(candidates, validation, qualification, cycle.seed))
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
            result = _FEEDBACK_RUNNERS[schedule](
                incumbent, cycle.candidates, cycle.validation, cycle.qualification, evaluate,
                metric_limit=_MAX_VALIDATION_READS, qualify=qualify, seed=cycle.seed,
            )
        results.append(result)
        schedules.append(schedule)
        incumbent = result.prompt
        rejected = (result.search.finalist is not None and result.qualification is not None
                    and result.qualification.status == 'rejected')
    return FeedbackEpisodeResult(incumbent, opening, training_reads, tuple(results), tuple(schedules))
