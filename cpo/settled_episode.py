"""Run the settled training-probe policy across fixed prompt pools."""

from dataclasses import dataclass, replace
from functools import partial

from .bounded_opening_repair import screen as opening_screen
from .bounded_uniform_validation import screen as bounded_screen
from .certified_shared_validation_cycle import SCHEDULES, _screen as certified_screen
from .fixed_pool_cycle import FixedPoolCycleResult
from .optimizer import Row
from .ordered_uniform_validation import MISSES, screen as uniform_screen
from .qualification_prefix_cycle import run_qualification_prefix_cycle
from .quoted_shared_validation_cycle import _screen as quoted_screen
from .settled_episode_schedule import choose_schedule
from .single_finalist import FinalistResult
from .two_sided_certificate_cycle import _run


@dataclass(frozen=True)
class EpisodeCycle:
    candidates: tuple[str, ...]
    validation: tuple[Row, ...]
    qualification: tuple[Row, ...]
    seed: int = 0


@dataclass(frozen=True)
class EpisodeResult:
    prompt: str
    schedule: str
    training_evaluations: int
    cycles: tuple[FixedPoolCycleResult, ...]

    @property
    def evaluations(self):
        return self.training_evaluations + sum(
            cycle.search.evaluations + cycle.qualification_evaluations for cycle in self.cycles
        )


_ACTIONS = ('fitted-opening-repair', 'uniform/8/18', 'successive-halving/4/6')
_MAX_VALIDATION_READS = 19


def _incumbent_first(incumbent, candidates, rows, evaluate, cap):
    widths = SCHEDULES['wide']
    critical = any(row.critical for row in rows)
    paid = {}

    def observe(prompt, row):
        key = prompt, row.id
        if key not in paid:
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Validation requires exact boolean replies')
            paid[key] = reply
        return paid[key]

    charge = sum(1 + min(len(candidates), width) for width, _ in zip(widths, rows))
    if candidates and cap >= charge and not critical:
        for row in rows[:len(widths)]:
            if not observe(incumbent, row).passed:
                break
        else:
            return FinalistResult(incumbent, None, len(paid)), None

    result, counts = certified_screen(
        incumbent, candidates, rows, observe, cap, widths=widths, margin=0,
    )
    if result.finalist is not None and not critical:
        grades = {key: reply.passed for key, reply in paid.items()}
        if not any(prompt == incumbent and not passed and grades.get((result.finalist, row_id))
                   for (prompt, row_id), passed in grades.items()):
            return FinalistResult(incumbent, None, len(paid)), None
    return replace(result, evaluations=len(paid)), counts


def _limit(screen, width, maximum, incumbent, candidates, rows, evaluate, cap):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, maximum))


_OPENING_HALVING = partial(_limit, partial(quoted_screen, halve=True), 8, 9)
_OPENING_LIMIT = partial(_limit, partial(opening_screen, opening_width=2, repair=False), 8, 9)
_RUNNERS = {
    _ACTIONS[0]: partial(
        run_qualification_prefix_cycle,
        screens=(_incumbent_first, _OPENING_HALVING, _OPENING_HALVING, _OPENING_LIMIT),
    ),
    _ACTIONS[1]: partial(_run, screen=partial(_limit, partial(uniform_screen, order=MISSES), 8, 18)),
    _ACTIONS[2]: partial(_run, screen=partial(_limit, partial(bounded_screen, halve=True), 4, 6)),
}


def run_settled_episode(incumbent, training_rows, cycles, evaluate, *, probe, qualify):
    """Pick one frozen schedule using two incumbent grades and carry it forward.

    Supply two training rows and one or more fixed cycles. Each cycle has an
    ordered roster of up to eight challengers, a validation panel of one to
    nineteen rows, and four qualification rows. Use distinct candidate prompts
    and row IDs throughout the episode. Only a qualified prompt carries
    forward. Grades must be stable within each cycle.

    `probe(prompt, row)` and `qualify(prompt, row, repeat)` return exact
    booleans. `evaluate(prompt, row)` returns an Observation. The result
    counts callbacks across all three roles. Held-out scoring is caller-owned.
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

    schedule = choose_schedule(incumbent, training_rows, observe, actions=_ACTIONS)
    run = _RUNNERS[schedule]
    results = []
    for cycle in prepared:
        result = run(
            incumbent, cycle.candidates, cycle.validation, cycle.qualification, evaluate,
            metric_limit=_MAX_VALIDATION_READS, qualify=qualify, seed=cycle.seed,
        )
        results.append(result)
        incumbent = result.prompt
    return EpisodeResult(incumbent, schedule, training_reads, tuple(results))
