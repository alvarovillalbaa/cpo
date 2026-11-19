"""Select a fully evaluated prompt from a finite pool under a lookup cap."""

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class PoolResult:
    prompt: str
    validation_passes: int
    evaluations: int


def select_pool(candidates, validation, evaluate, *, metric_limit, screen_rows=0, max_challenges=None,
                adaptive_rejection=False):
    """Race a fixed pool, optionally ordering challengers on a common prefix.

    The first candidate is the incumbent. A challenger needs a strictly higher
    exact score and must preserve the original incumbent's critical passes.
    Adaptive rejection uses measured screen outcomes, requires enough budget
    to finish a challenge, and checks validation rows with lower observed
    pass rates first.
    """
    candidates, validation = tuple(candidates), tuple(validation)
    if not candidates or len(set(candidates)) != len(candidates):
        raise ValueError('Pool requires distinct candidates and an incumbent')
    if not validation or len({row.id for row in validation}) != len(validation):
        raise ValueError('Pool selection requires distinct, nonempty validation rows')
    if type(metric_limit) is not int or metric_limit < len(validation):
        raise ValueError('The budget must cover the incumbent')
    if type(screen_rows) is not int or not 0 <= screen_rows <= len(validation):
        raise ValueError('Screen size must fit within validation')
    if max_challenges is not None and (type(max_challenges) is not int or max_challenges < 1):
        raise ValueError('A shortlist must allow at least one challenge')
    if screen_rows and len(candidates) > 1:
        minimum = len(candidates) * screen_rows + 2 * (len(validation) - screen_rows)
        if metric_limit < minimum:
            raise ValueError('Budget must fund the screen and a complete first challenge')

    observations = {}
    successes, counts = Counter(), Counter()

    def observe(prompt, row):
        key = prompt, row.id
        if key not in observations:
            result = evaluate(prompt, row).passed
            if type(result) is not bool:
                raise ValueError('Pool observations require an exact boolean outcome')
            observations[key] = result
            if adaptive_rejection:
                successes[row.id] += result
                counts[row.id] += 1
        return observations[key]

    leader, *challengers = candidates
    leader_passes = {row.id for row in validation if observe(leader, row)}
    protected = {row.id for row in validation if row.critical and row.id in leader_passes}
    if screen_rows and len(leader_passes) < len(validation):
        screened = {prompt: sum(observe(prompt, row) for row in validation[:screen_rows])
                    for prompt in challengers}
        challengers.sort(key=screened.__getitem__, reverse=True)
    for prompt in challengers[:max_challenges]:
        if len(leader_passes) == len(validation):
            break
        if adaptive_rejection:
            if any(observations.get((prompt, row_id)) is False for row_id in protected):
                continue
            passed = {row.id for row in validation if observations.get((prompt, row.id)) is True}
            unknown = [row for row in validation if (prompt, row.id) not in observations]
            remaining_budget = metric_limit - len(observations)
            if len(unknown) > remaining_budget or len(passed) + len(unknown) <= len(leader_passes):
                continue
            ordered = sorted(unknown, key=lambda row: (
                row.id not in protected, Fraction(successes[row.id] + 1, counts[row.id] + 2)))
        else:
            passed = set()
            ordered = sorted(validation, key=lambda row: (row.id not in protected, row.id in leader_passes))
        for count, row in enumerate(ordered, 1):
            if len(observations) >= metric_limit and (prompt, row.id) not in observations:
                break
            if observe(prompt, row):
                passed.add(row.id)
            elif row.id in protected:
                break
            if len(passed) + len(ordered) - count <= len(leader_passes):
                break
        else:
            leader, leader_passes = prompt, passed
    return PoolResult(leader, len(leader_passes), len(observations))
