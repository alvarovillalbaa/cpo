"""Validation-routed episodes with an exact nominee certificate on narrow pools."""

from dataclasses import replace
from functools import lru_cache, partial

from ..feedback_episode import FeedbackEpisodeResult, _FOLLOW_UP, _RETAIN
from ..fixed_pool_cycle import FixedPoolCycleResult
from ..ordered_uniform_validation import MISSES, screen as ordered_screen
from ..quoted_shared_validation_cycle import _schedule
from ..settled_episode import EpisodeCycle, _MAX_VALIDATION_READS
from ..settled_episode_schedule import choose_schedule
from ..single_finalist import FinalistResult
from ..two_sided_certificate_cycle import _run
from . import _cycle
from .validation_routing import _ACTIONS, _UNIFORM


__all__ = ['run_certified_nomination_episode']
_UNIFORM_CAP = 18


def _winner(depth, state):
    base, first, second = state
    if base[0] >= depth - min(first[1], second[1]):
        return 0
    if first[0] > depth - base[1] and first[0] >= depth - second[1]:
        return 1
    if second[0] > max(depth - base[1], depth - first[1]):
        return 2
    return None


def _advance(state, side, passed):
    passes, misses = state[side]
    return state[:side] + ((passes + passed, misses + (not passed)),) + state[side + 1:]


@lru_cache(maxsize=32_768)
def _next_read(depth, state):
    if _winner(depth, state) is not None:
        return 0, None
    options = []
    for side, (passes, misses) in enumerate(state):
        if passes + misses == depth or (side and depth - misses <= state[0][0]):
            continue
        hit = _next_read(depth, _advance(state, side, True))[0]
        miss = _next_read(depth, _advance(state, side, False))[0]
        expected = (hit * (passes + 1) + miss * (misses + 1)) / (passes + misses + 2)
        options.append((1 + expected, side))
    return min(options)


def _screen(incumbent, candidates, rows, evaluate, cap, *, prepaid, use_validation_rates):
    cap = min(cap, _UNIFORM_CAP)
    funded = tuple(row for row, _ in _schedule(len(candidates), rows, cap, False))
    depth = len(funded)
    if not 3 <= depth <= 6:
        return ordered_screen(incumbent, candidates, rows, evaluate, cap, order=MISSES)

    prompts = (incumbent, *candidates)
    state = ((0, 0),) * len(prompts)
    seen = ({}, {}, {})

    def observe(side, row):
        nonlocal state
        grade = evaluate(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('An exact nominee certificate requires boolean grades')
        state = _advance(state, side, grade)
        seen[side][row.id] = grade

    for row in funded:
        if row.id in prepaid:
            observe(0, row)
    for paid in range(sum(map(len, seen)), depth * len(prompts) + 1):
        winner = _winner(depth, state)
        if winner == 0:
            return FinalistResult(incumbent, None, paid), None
        if winner is not None:
            counts = tuple((state[side][0], sum(state[side])) for side in (0, winner))
            nominee = prompts[winner]
            return FinalistResult(nominee, nominee, paid), counts if use_validation_rates else ((0, 0), (0, 0))
        _, side = _next_read(depth, state)
        pending = [row for row in funded if row.id not in seen[side]]
        row = min(pending, key=lambda row: seen[0].get(row.id) is not False) if side else pending[0]
        observe(side, row)
    raise RuntimeError('The full funded panel must settle the nominee')


def _prepare(incumbent, cycles):
    cycles = tuple(EpisodeCycle(tuple(cycle.candidates), tuple(cycle.validation),
                                tuple(cycle.qualification), cycle.seed) for cycle in cycles)
    if not cycles:
        raise ValueError('Supply at least one cycle')
    row_ids, prompts = [], [incumbent]
    for cycle in cycles:
        if (len(cycle.candidates) > 8 or not 1 <= len(cycle.validation) <= _MAX_VALIDATION_READS
                or len(cycle.qualification) != 4):
            raise ValueError('Each cycle requires up to eight challengers, 1–19 validation rows and four qualification rows')
        row_ids.extend(row.id for row in (*cycle.validation, *cycle.qualification))
        prompts.extend(cycle.candidates)
    if len(set(row_ids)) != len(row_ids) or len(set(prompts)) != len(prompts):
        raise ValueError('The episode requires disjoint row IDs and distinct prompts')
    return cycles


def run_certified_nomination_episode(incumbent, cycles, evaluate, *, qualify, use_validation_rates=True):
    """Route an episode and stop eligible uniform screens at an exact nominee.

    Supply distinct prompts and row IDs, one to nineteen validation cases,
    and four independent qualification cases per cycle. The opening probes
    at most two incumbent validation cases. A noncritical uniform screen
    with two challengers and three to six funded cases can finish once no
    unread reply could change its nominee under the original tie order.

    With stable replies, the nominee and independent qualification decision
    match ordinary validation routing. Paid validation rates order the
    independent reads. Set ``use_validation_rates=False`` for neutral rates
    on these certificate screens. Other schedules, critical validation,
    qualification thresholds, and accounting use the ordinary rules.
    """
    if type(use_validation_rates) is not bool:
        raise ValueError('use_validation_rates must be a bool')
    cycles = _prepare(incumbent, cycles)
    first, prefix, reused = cycles[0], {}, set()
    first_reads = 0

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

    start = incumbent

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
            screen = partial(_screen, prepaid=() if index else prefix, use_validation_rates=use_validation_rates)
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
