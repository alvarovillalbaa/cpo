"""Limit independent admission attempts across a fixed sequence of witness cycles."""

from dataclasses import dataclass

from ..fixed_pool_cycle import FixedPoolCycleResult
from ..optimizer import Row
from . import run_rotating_witness_cycle


__all__ = ['WitnessCycle', 'WitnessEpisodeResult', 'run_rotating_witness_episode']


@dataclass(frozen=True)
class WitnessCycle:
    candidates: tuple[str, ...]
    validation: tuple[Row, ...]
    qualification: tuple[Row, ...]
    seed: int = 0


@dataclass(frozen=True)
class WitnessEpisodeResult:
    prompt: str
    cycles: tuple[FixedPoolCycleResult, ...]
    admission_attempts: int


def run_rotating_witness_episode(incumbent, cycles, evaluate, *, qualify, metric_limit, max_admissions=1,
                                 repeats=1, minimum_gain=1, qualification_limit=None):
    """Stop opening cycles when the episode has used its admission attempts.

    All scheduled qualification case IDs must be distinct and disjoint from
    every validation panel. A nomination consumes one attempt even when
    qualification rejects it or runs out of budget. A cycle with no nominee
    consumes no admission attempt. The evaluator controls any reply reuse.
    """
    if type(max_admissions) is not int or max_admissions < 0:
        raise ValueError('The admission-attempt cap must be a nonnegative integer')
    # Materialize the entire schedule before the first callback so future
    # qualification cases cannot leak into an earlier validation panel.
    schedule = tuple(WitnessCycle(tuple(cycle.candidates), tuple(cycle.validation), tuple(cycle.qualification), cycle.seed)
                     for cycle in cycles)
    validation = set()
    qualification = set()
    for cycle in schedule:
        valid = {row.id for row in cycle.validation}
        fresh = {row.id for row in cycle.qualification}
        if (not valid or not fresh or len(valid) != len(cycle.validation) or len(fresh) != len(cycle.qualification)
                or fresh & qualification):
            raise ValueError('Each cycle needs distinct validation and fresh qualification case IDs')
        if len(set(cycle.candidates)) != len(cycle.candidates):
            raise ValueError('Each cycle needs distinct challenger prompts')
        validation.update(valid)
        qualification.update(fresh)
    if validation & qualification:
        raise ValueError('Episode validation and qualification case IDs must be disjoint')

    results = []
    attempts = 0
    for cycle in schedule:
        if attempts == max_admissions:
            break
        candidates = (candidate for candidate in cycle.candidates if candidate != incumbent)
        result = run_rotating_witness_cycle(incumbent, candidates, cycle.validation, cycle.qualification, evaluate,
                                            metric_limit=metric_limit, qualify=qualify, repeats=repeats,
                                            minimum_gain=minimum_gain, seed=cycle.seed,
                                            qualification_limit=qualification_limit)
        attempts += result.qualification is not None
        incumbent = result.prompt
        results.append(result)
    return WitnessEpisodeResult(incumbent, tuple(results), attempts)
