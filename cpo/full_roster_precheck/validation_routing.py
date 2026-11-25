"""Choose a full-roster CPO opening using the first incumbent validation grades."""

from dataclasses import replace

from ..settled_episode import EpisodeCycle, _MAX_VALIDATION_READS
from ..settled_episode_schedule import choose_schedule
from .fixed_opening import run_fixed_opening_episode


__all__ = ['run_validation_routed_episode']

_UNIFORM = 'uniform/8/18'
_ACTIONS = (_UNIFORM, _UNIFORM, 'successive-halving/4/6')


def run_validation_routed_episode(incumbent, cycles, evaluate, *, qualify):
    """Choose uniform on a validation miss or narrow halving after two passes.

    The opening reads up to two incumbent validation rows. The chosen screen
    reuses those replies when it asks for the same prompt and row. Each
    physical lookup, including an unused routing reply, counts toward the
    first-cycle validation cap of 19. Qualification uses disjoint rows.

    Supply at least one EpisodeCycle. Each cycle needs up to eight ordered
    challengers, one to nineteen validation rows and four qualification rows.
    Every row ID and prompt must be distinct across cycles. An empty opening
    roster, fewer than two opening validation rows or a critical opening
    validation row uses the fixed uniform runner without routing reads.

    The runner requires stable grades, buys no training replies, and returns
    the usual feedback result with the selected schedule and actual counts.
    """
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

    first = prepared[0]
    if len(first.validation) < 2 or not first.candidates or any(row.critical for row in first.validation):
        return run_fixed_opening_episode(incumbent, prepared, evaluate, schedule=_UNIFORM, qualify=qualify)

    prefix, reused = {}, set()
    first_ids = {row.id for row in first.validation}
    first_reads = 0

    def fetch(prompt, row):
        nonlocal first_reads
        if row.id in first_ids:
            if first_reads == _MAX_VALIDATION_READS:
                raise ValueError('The routing prefix and selected screen exhausted the first-cycle search cap')
            first_reads += 1
        return evaluate(prompt, row)

    def opening_grade(prompt, row):
        reply = fetch(prompt, row)
        prefix[row.id] = reply
        return reply.passed

    def read(prompt, row):
        if prompt == incumbent and row.id in prefix:
            reused.add(row.id)
            return prefix[row.id]
        return fetch(prompt, row)

    schedule = choose_schedule(incumbent, first.validation[:2], opening_grade, actions=_ACTIONS)
    result = run_fixed_opening_episode(incumbent, prepared, read, schedule=schedule, qualify=qualify)
    first_result = result.cycles[0]
    if first_result.search.evaluations + len(prefix.keys() - reused) != first_reads:
        raise ValueError('Every routed first-cycle validation reply must reconcile')
    accounted = replace(first_result, search=replace(first_result.search, evaluations=first_reads))
    return replace(result, cycles=(accounted, *result.cycles[1:]))
