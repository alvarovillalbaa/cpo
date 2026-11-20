"""Use the native cached rewrite's first minibatch with bounded field scoring."""

from functools import cache

from benchmarks.gepa_cached_opening import select_opening
from cpo import Observation, Row
from cpo.paired_field_rewrite import select_paired_field_rewrite


@cache
def first_minibatch(size, seed, width):
    """Resolve the seeded batch with synthetic scores and no provider access."""
    validation = [{'id': str(index), 'expected': {'pass': True}} for index in range(size)]
    reads = []

    def evaluate(prompt, case):
        if prompt == 'rewrite':
            reads.append(int(case))
        return Observation(False, {}, 0)

    selected = select_opening('start', ('rewrite',), {'validation': validation}, evaluate,
                              cap=2 * size, seed=seed, width=1, minibatch_size=width)
    if selected != 'start' or len(reads) != width or len(set(reads)) != width:
        raise ValueError('The native cached rewrite no longer has the expected first minibatch')
    return tuple(reads)


def select(initial, bank, groups, evaluate, *, cap, seed, minibatch_size, observed_charge=None):
    validation = tuple(Row(row['id'], 'validation', fields=len(row['expected'])) for row in groups['validation'])
    if cap < 2 * len(validation):
        raise ValueError('The paired opening requires a fully funded two-prompt validation')
    batch = tuple(validation[index].id for index in first_minibatch(len(validation), seed, minibatch_size))
    return select_paired_field_rewrite(initial, bank[0], validation, batch,
                                       lambda prompt, row: evaluate(prompt, row.id), observed_charge=observed_charge)
