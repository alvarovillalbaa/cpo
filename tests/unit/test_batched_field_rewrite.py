from random import Random

from benchmarks.batched_field_feedback import compare_search
from cpo import Observation


def test_batched_field_choices_and_feedback_match_native_across_rounds():
    groups = {split: tuple({'id': f'{split}-{idx}', 'expected': {'a': 1, 'b': 1, 'c': 1}}
                           for idx in range(5)) for split in ('train', 'validation')}
    prompts = ('start', 'a', 'b', 'c', 'd')
    seen = set()
    for seed in range(12):
        rng = Random(seed)
        grades = {(prompt, row['id']): rng.randrange(4) for prompt in prompts
                  for rows in groups.values() for row in rows}

        def evaluate(prompt, case):
            fields = grades[prompt, case]
            return Observation(fields == 3, {'id': case, 'observed': str(fields)}, fields)

        def run(cap, paired):
            # Propose the same child twice in one round and permit the next
            # round to revisit an older candidate through a different parent.
            later = iter(('c', 'c', 'd', 'a'))

            def reflect(_parent, _feedback):
                return next(later)

            return compare_search('start', ('a', 'b'), groups, evaluate, reflect, cap=cap, seed=seed, paired=paired)

        for cap in (23, 40, 72):
            before, trace, paid, proposals = run(cap, False)
            after, paired_trace, paired_paid, paired_proposals = run(cap, True)
            assert (after, paired_trace, paired_proposals) == (before, trace, proposals)
            assert len(paired_paid) == len(set(paired_paid))
            assert set(paired_paid) <= set(paid)
            assert len(paid) <= cap
            if len(paired_paid) < len(paid):
                seen.add('saved')
            if any(parent != 'start' for _, parent, _ in trace):
                seen.add('changed-parent')
            if len(proposals) >= 4:
                seen.add('later-rounds')
    assert seen == {'saved', 'changed-parent', 'later-rounds'}
