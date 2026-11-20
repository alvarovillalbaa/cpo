"""Check both paired gain gates over all binary profiles on four cases."""

from itertools import product

import pytest

from cpo import Observation, Row
from cpo.paired_rewrite import select_paired_rewrite, select_same_parent_rewrites, select_sequential_rewrites


@pytest.mark.parametrize('priced', (False, True))
def test_paid_reads_are_a_subset_of_complete_native_gates(priced):
    validation = tuple(Row(str(i), f'family-{i}', critical=True) for i in range(4))
    batch = ('2', '0')
    for bits in product((False, True), repeat=8):
        outcomes = dict(zip(product(('start', 'rewrite'), (row.id for row in validation)), bits, strict=True))
        paid = []

        def evaluate(prompt, row):
            assert row is validation[int(row.id)]
            paid.append((prompt, row.id))
            return Observation(outcomes[prompt, row.id], {})

        old = sum(bits[:4])
        new = sum(bits[4:])
        gain = sum(int(outcomes['rewrite', case]) - int(outcomes['start', case]) for case in batch)
        expected = 'rewrite' if gain > 0 and new > old else 'start'
        def price(prompt, row, reply):
            assert paid[-1] == (prompt, row.id) and reply.passed == outcomes[prompt, row.id]
            return 1 + int(row.id) + (prompt == 'rewrite')

        assert select_paired_rewrite('start', 'rewrite', validation, batch, evaluate,
                                     observed_charge=price if priced else None) == expected
        complete = {('start', row.id) for row in validation}
        if old < len(validation):
            complete.update(('rewrite', case) for case in batch)
        if gain > 0:
            complete.update(('rewrite', row.id) for row in validation)
        assert len(paid) == len(set(paid))
        assert set(paid) <= complete


def test_charges_reorder_full_validation_after_the_same_minibatch():
    rows = tuple(Row(str(i), 'archive') for i in range(4))

    def read(observed_charge):
        paid = []

        def evaluate(prompt, row):
            paid.append((prompt, row.id))
            return Observation(prompt == 'rewrite', {})

        assert select_paired_rewrite('start', 'rewrite', rows, ('2', '0'), evaluate,
                                     observed_charge=observed_charge) == 'rewrite'
        return paid

    old = read(lambda prompt, *_: 1 if prompt == 'start' else 10)
    new = read(lambda prompt, *_: 1 if prompt == 'rewrite' else 10)
    assert old[:3] == new[:3] == [('start', '2'), ('rewrite', '2'), ('start', '0')]
    assert old[3] == ('start', '1')
    assert new[3] == ('rewrite', '0')
    assert read(lambda *_: None) == read(lambda *_: 0) == read(lambda *_: 1)


def test_invalid_charge_fails_after_the_observed_reply():
    paid = []

    def evaluate(prompt, row):
        paid.append((prompt, row.id))
        return Observation(False, {})

    with pytest.raises(ValueError, match='nonnegative integers'):
        select_paired_rewrite('start', 'rewrite', (Row('known', 'family'),), ('known',), evaluate,
                              observed_charge=lambda *_: -1)
    assert paid == [('start', 'known')]


def test_minibatch_requires_distinct_known_cases_before_reading():
    validation = (Row('known', 'family'),)
    for batch in ((), ('unknown',), ('known', 'known')):
        with pytest.raises(ValueError, match='nonempty subset'):
            select_paired_rewrite('start', 'rewrite', validation, batch, lambda *_: pytest.fail('Read a case'))


@pytest.mark.parametrize('priced', (False, True))
def test_same_parent_selection_matches_batched_native_gates(priced):
    case_ids = ('0', '1', '2', '3')
    rows = tuple(Row(case, 'archive') for case in case_ids)
    proposals = (('first', ('2', '0')), ('second', ('1', '2')))
    prompts = ('start', 'first', 'second')
    keys = tuple(product(prompts, case_ids))
    for bits in product((False, True), repeat=len(keys)):
        outcomes = dict(zip(keys, bits, strict=True))
        totals = {prompt: sum(outcomes[prompt, case] for case in case_ids) for prompt in prompts}
        accepted = ['start']
        complete = {('start', case) for case in case_ids}
        if totals['start'] < len(rows):
            for prompt, batch in proposals:
                complete.update((prompt, case) for case in batch)
                if sum(outcomes[prompt, case] for case in batch) > sum(outcomes['start', case] for case in batch):
                    accepted.append(prompt)
                    complete.update((prompt, case) for case in case_ids)
        paid = []

        def evaluate(prompt, row):
            assert row is rows[int(row.id)]
            paid.append((prompt, row.id))
            return Observation(outcomes[prompt, row.id], {})

        def price(prompt, row, reply):
            assert paid[-1] == (prompt, row.id) and reply.passed == outcomes[prompt, row.id]
            return None if prompt == 'first' and row.id == '2' else 1 + int(row.id) + prompts.index(prompt)

        selected = select_same_parent_rewrites('start', proposals, rows, evaluate,
                                              observed_charge=price if priced else None)
        assert selected == max(accepted, key=totals.get)
        assert len(paid) == len(set(paid))
        assert set(paid) <= complete


def test_same_parent_validates_every_proposal_before_reading():
    rows = (Row('known', 'family'),)
    first = ('first', ('known',))
    for proposals in ((first, first), (first, ('start', ('known',))), (first, ('second', ('unknown',)))):
        with pytest.raises(ValueError):
            select_same_parent_rewrites('start', proposals, rows, lambda *_: pytest.fail('Read a case'))


@pytest.mark.parametrize('priced', (False, True))
def test_sequential_pool_keeps_minibatch_improvements_regardless_of_full_score(priced):
    cases = ('0', '1', '2', '3')
    rows = tuple(Row(case, 'archive') for case in cases)
    batches = (('0', '2'), ('1', '2'))
    initial, first, second = prompts = ('start', 'first', 'second')
    keys = tuple(product(prompts, cases))

    for bits in product((False, True), repeat=len(keys)):
        outcomes = dict(zip(keys, bits, strict=True))
        totals = {prompt: sum(outcomes[prompt, case] for case in cases) for prompt in prompts}
        pool, schedule_calls, proposal_calls = [initial], [], []
        native_reads = {(initial, case) for case in cases}
        for index, (rewrite, batch) in enumerate(zip((first, second), batches, strict=True)):
            if max(totals[prompt] for prompt in pool) == len(cases):
                break
            # An accepted rewrite can parent another even when its overall score is lower.
            parent = pool[-1]
            schedule_calls.append((index, tuple(pool)))
            before = sum(outcomes[parent, case] for case in batch)
            if before < len(batch):
                proposal_calls.append((index, parent))
            native_reads.update((rewrite, case) for case in batch)
            if sum(outcomes[rewrite, case] for case in batch) > before:
                pool.append(rewrite)
                native_reads.update((rewrite, case) for case in cases)
        paid, actual_schedule, actual_proposals = [], [], []

        def evaluate(prompt, row):
            assert row is rows[int(row.id)]
            paid.append((prompt, row.id))
            return Observation(outcomes[prompt, row.id], {'source': prompt})

        def schedule(index, tracked, grades):
            actual_schedule.append((index, tracked))
            if len(tracked) > 1:
                for prompt in tracked:
                    assert grades(prompt) == tuple(outcomes[prompt, case] for case in cases)
            return tracked[-1], batches[index]

        def propose(index, parent, examples):
            actual_proposals.append((index, parent))
            assert tuple(row.id for row, _ in examples) == batches[index]
            for row, reply in examples:
                assert reply.feedback['source'] == parent and reply.passed == outcomes[parent, row.id]
                assert (parent, row.id) in paid
            return (first, second)[index]

        def price(prompt, row, _reply):
            assert paid[-1] == (prompt, row.id)
            return 1 + int(row.id) + prompts.index(prompt)

        chosen = select_sequential_rewrites(initial, rows, evaluate, schedule, propose, rounds=2,
                                             observed_charge=price if priced else None)
        assert chosen == max(pool, key=totals.get)
        assert actual_schedule == schedule_calls and actual_proposals == proposal_calls
        assert len(paid) == len(set(paid)) and set(paid) <= native_reads
