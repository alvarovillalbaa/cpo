"""Run validation-routed CPO with a cap on first-gain certification."""

from dataclasses import replace
from functools import lru_cache, partial

from ..feedback_episode import FeedbackEpisodeResult, _FOLLOW_UP, _RETAIN
from ..fixed_pool_cycle import FixedPoolCycleResult
from ..quoted_shared_validation_cycle import _schedule
from ..settled_episode import _MAX_VALIDATION_READS
from ..settled_episode_schedule import choose_schedule
from ..single_finalist import FinalistResult
from ..two_sided_certificate_cycle import _run
from . import _cycle
from .certified_nomination import _advance, _prepare, _screen as exact_screen, _UNIFORM_CAP
from .validation_routing import _ACTIONS, _UNIFORM


__all__ = ['run_first_gain_episode']


def _strict_winner(depth, state):
    upper = depth - state[0][1]
    return next((side for side in (1, 2) if state[side][0] > upper), None)


@lru_cache(maxsize=131_072)
def _choose_read(depth, state, allowance):
    """Maximize estimated proof probability, then minimize expected reads."""
    if _strict_winner(depth, state) is not None:
        return 1.0, 0.0, None
    base_passes, base_misses = state[0]
    possible = tuple(side for side in (1, 2) if depth - state[side][1] > base_passes)
    if not possible or all(depth - base_misses - state[side][0] >= allowance for side in possible):
        return 0.0, 0.0, None

    options = []
    for side in (0, *possible):
        passes, misses = state[side]
        if passes + misses == depth:
            continue
        hit, miss = (_choose_read(depth, _advance(state, side, grade), allowance - 1)
                     for grade in (True, False))
        rate = (passes + 1) / (passes + misses + 2)
        chance = rate * hit[0] + (1 - rate) * miss[0]
        expected_reads = 1 + rate * hit[1] + (1 - rate) * miss[1]
        options.append((chance, expected_reads, side))
    return min(options, key=lambda option: (-round(option[0], 14), round(option[1], 12), option[2]))


def _screen(incumbent, candidates, rows, evaluate, cap, *, prepaid, read_limit):
    funded = tuple(row for row, _ in _schedule(len(candidates), rows, min(cap, _UNIFORM_CAP), False))
    depth = len(funded)
    if not 3 <= depth <= 6:
        return exact_screen(incumbent, candidates, rows, evaluate, cap, prepaid=prepaid, use_validation_rates=True)

    prompts = (incumbent, *candidates)
    state = ((0, 0),) * len(prompts)
    seen = ({}, {}, {})

    def observe(side, row):
        nonlocal state
        grade = evaluate(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('Strict validation certificates require boolean grades')
        state = _advance(state, side, grade)
        seen[side][row.id] = grade

    for row in funded:
        if row.id in prepaid:
            observe(0, row)
    spent = sum(map(len, seen))
    limit = min(read_limit, depth * len(prompts), cap)
    while True:
        winner = _strict_winner(depth, state)
        if winner is not None:
            nominee = prompts[winner]
            counts = tuple((state[side][0], sum(state[side])) for side in (0, winner))
            return FinalistResult(nominee, nominee, spent), counts
        _, _, side = _choose_read(depth, state, limit - spent)
        if side is None:
            return FinalistResult(incumbent, None, spent), None
        pending = (row for row in funded if row.id not in seen[side])
        row = min(pending, key=lambda row: seen[0].get(row.id) is not False) if side else next(pending)
        observe(side, row)
        spent += 1


def run_first_gain_episode(incumbent, cycles, evaluate, *, qualify, uniform_read_limit=18):
    """Qualify the first challenger to prove a strict full-panel validation gain.

    Supply disjoint validation and qualification row IDs and distinct prompts
    across cycles. Each cycle accepts up to eight ordered challengers, one to
    nineteen validation rows and four independent qualification rows. Replies
    must remain stable. The usual qualification and schedule transitions apply.

    The 2–18 read limit applies to noncritical uniform screens with two
    challengers and three to six funded cases. It counts prepaid opening
    grades. Other screens use their existing budgets. Every deployment
    requires independent qualification. The returned feedback receipt lists
    each cycle's schedule, nominee, deployment and callback counts.
    """
    if type(uniform_read_limit) is not int or not 2 <= uniform_read_limit <= _UNIFORM_CAP:
        raise ValueError('uniform_read_limit must be an integer from 2 through 18')
    cycles = _prepare(incumbent, cycles)
    first, prefix, reused = cycles[0], {}, set()
    start, first_reads = incumbent, 0

    def fetch_first(prompt, row):
        nonlocal first_reads
        if first_reads == _MAX_VALIDATION_READS:
            raise ValueError('The opening probes and screen exceeded the first-cycle search cap')
        first_reads += 1
        return evaluate(prompt, row)

    def opening_grade(prompt, row):
        reply = fetch_first(prompt, row)
        prefix[row.id] = reply
        return reply.passed

    def read_first(prompt, row):
        if prompt == start and row.id in prefix:
            reused.add(row.id)
            return prefix[row.id]
        return fetch_first(prompt, row)

    opening = _UNIFORM
    if len(first.validation) >= 2 and first.candidates and not any(row.critical for row in first.validation):
        opening = choose_schedule(start, first.validation[:2], opening_grade, actions=_ACTIONS)

    rejected = False
    results, schedules = [], []
    for index, cycle in enumerate(cycles):
        schedule = _FOLLOW_UP[opening] if rejected else opening
        read = evaluate if index else read_first
        if schedule == _RETAIN:
            result = FixedPoolCycleResult(FinalistResult(incumbent, None, 0), None)
        elif schedule == _UNIFORM and len(cycle.candidates) == 2 and not any(row.critical for row in cycle.validation):
            screen = partial(_screen, prepaid=() if index else prefix, read_limit=uniform_read_limit)
            result = _run(incumbent, cycle.candidates, cycle.validation, cycle.qualification, read,
                          metric_limit=_MAX_VALIDATION_READS, qualify=qualify, seed=cycle.seed, screen=screen)
        else:
            result = _cycle(schedule, incumbent, cycle, read, qualify)
        if not index:
            if result.search.evaluations + len(prefix.keys() - reused) != first_reads:
                raise ValueError('Every first-cycle validation reply must reconcile')
            result = replace(result, search=replace(result.search, evaluations=first_reads))
        results.append(result)
        schedules.append(schedule)
        incumbent = result.prompt
        rejected = (result.search.finalist is not None and result.qualification is not None
                    and result.qualification.status == 'rejected')
    return FeedbackEpisodeResult(incumbent, opening, 0, tuple(results), tuple(schedules))
