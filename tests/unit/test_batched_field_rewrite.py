from random import Random

from benchmarks.batched_field_feedback import compare_search
from cpo import Observation, Row
from cpo.batched_field_rewrite import select_batched_field_rewrites
from cpo.sequential_field_rewrite import SequentialSearchBudget


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


def test_quote_reserves_both_proposals_and_unread_validation_before_a_batch():
    training = (Row('t1', 'fixture', fields=1), Row('t2', 'fixture', fields=1))
    validation = (Row('v1', 'fixture', fields=1), Row('v2', 'fixture', fields=1))

    def run(limit, *, repeated=False, proposal_limit=None):
        settled, proposals = [], []

        def evaluate(prompt, _row):
            assert sum(settled) + 5 <= limit
            settled.append(5)
            passed = prompt == 'first'
            return Observation(passed, {}, int(passed))

        def schedule(_index, _pool, _grades):
            return 'start', (('t1',), ('t1' if repeated else 't2',))

        def propose(index, _parent, _observations):
            assert sum(settled) + 7 <= limit
            settled.append(7)
            proposals.append(index)
            return 'first' if index == 0 else 'start'

        budget = SequentialSearchBudget(limit, 5, lambda *_: 7, lambda *_: 7, proposal_limit=proposal_limit)
        selected = select_batched_field_rewrites(
            'start', training, validation, evaluate, schedule, propose, rounds=1, width=2,
            minibatch_size=1, metric_limit=10, observed_charge=lambda *_: 5, price_budget=budget,
        )
        return selected, proposals, sum(settled)

    assert run(9) == ('start', [], 0)
    assert run(63) == ('start', [], 5)
    assert run(64)[:2] == ('first', [0, 1])
    assert run(59, repeated=True)[:2] == ('first', [0, 1])
    assert run(100, proposal_limit=13) == ('start', [], 5)
    assert run(100, proposal_limit=14)[:2] == ('first', [0, 1])
