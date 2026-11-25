"""Run full-roster CPO with a caller-selected opening and no training probes."""

from ..feedback_episode import FeedbackEpisodeResult, _FOLLOW_UP, _RETAIN
from ..fixed_pool_cycle import FixedPoolCycleResult
from ..settled_episode import EpisodeCycle, _ACTIONS, _MAX_VALIDATION_READS
from ..single_finalist import FinalistResult
from . import _cycle


FIXED_OPENING_SCHEDULES = _ACTIONS
__all__ = ['FIXED_OPENING_SCHEDULES', 'run_fixed_opening_episode']


def run_fixed_opening_episode(incumbent, cycles, evaluate, *, schedule, qualify):
    """Run the full-roster feedback policy from a preselected opening schedule.

    Each cycle accepts up to eight challengers, one to nineteen validation
    rows, and four independent qualification rows. Row IDs and candidate
    prompts must be distinct throughout the episode. Choose the schedule
    before calling the runner, for example on separate calibration cases.

    The opening buys no training replies. Validation and qualification use
    the existing full-roster rules and require stable grades. A rejected
    finalist selects the existing feedback follow-up for the next cycle.
    The returned feedback receipt includes each schedule, decision, and
    actual callback count.
    """
    if schedule not in FIXED_OPENING_SCHEDULES:
        raise ValueError('Select a schedule from FIXED_OPENING_SCHEDULES')

    prepared = tuple(EpisodeCycle(tuple(cycle.candidates), tuple(cycle.validation),
                                 tuple(cycle.qualification), cycle.seed) for cycle in cycles)
    if not prepared:
        raise ValueError('Supply at least one cycle')

    row_ids, prompts = [], [incumbent]
    for cycle in prepared:
        if (len(cycle.candidates) > 8 or not 1 <= len(cycle.validation) <= _MAX_VALIDATION_READS
                or len(cycle.qualification) != 4):
            raise ValueError('Each cycle requires up to eight challengers, 1–19 validation rows and four qualification rows')
        row_ids.extend(row.id for row in (*cycle.validation, *cycle.qualification))
        prompts.extend(cycle.candidates)
    if len(set(row_ids)) != len(row_ids) or len(set(prompts)) != len(prompts):
        raise ValueError('The episode requires disjoint row IDs and distinct prompts')

    rejected = False
    results, schedules = [], []
    for cycle in prepared:
        current = _FOLLOW_UP[schedule] if rejected else schedule
        if current == _RETAIN:
            result = FixedPoolCycleResult(FinalistResult(incumbent, None, 0), None)
        else:
            result = _cycle(current, incumbent, cycle, evaluate, qualify)
        results.append(result)
        schedules.append(current)
        incumbent = result.prompt
        rejected = (result.search.finalist is not None and result.qualification is not None
                    and result.qualification.status == 'rejected')

    return FeedbackEpisodeResult(incumbent, schedule, 0, tuple(results), tuple(schedules))
