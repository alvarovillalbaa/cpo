"""Verify feedback-driven generations and the native sequential reserve."""

import pytest

from cpo import Observation, Row
from cpo.sequential_field_rewrite import SequentialSearchBudget, select_sequential_field_rewrites


@pytest.mark.parametrize(('limit', 'winner', 'generations'), ((19, 'start', 1), (20, 'repair-second', 2)))
def test_repair_generated_from_the_paid_feedback_of_a_lower_scoring_parent(limit, winner, generations):
    training = tuple(Row(f't{case}', 'task', fields=3) for case in range(4))
    validation = tuple(Row(f'v{case}', 'task', fields=3) for case in range(4))
    matches = {
        'start': (0, 1, 0, 0, 3, 1, 0, 0),
        'repair-first': (2, 2, 1, 1, 0, 0, 1, 1),
        'repair-second': (2, 2, 2, 3, 3, 3, 3, 2),
    }
    columns = {row.id: index for index, row in enumerate(training + validation)}
    reads, proposals = [], []

    def evaluate(prompt, row):
        reads.append((prompt, row.id))
        grade = matches[prompt][columns[row.id]]
        diagnosis = 'first' if row.id in ('t0', 't1') else 'second'
        return Observation(grade == row.fields, {'diagnosis': diagnosis, 'parent': prompt}, grade)

    def schedule(index, pool, grades):
        if index == 0:
            assert pool == ('start',)
            return 'start', ('t0', 't1')
        assert pool == ('start', 'repair-first')
        assert sum(grades('start')) > sum(grades('repair-first'))
        return 'repair-first', ('t2', 't3')

    def propose(index, parent, samples):
        assert all(row in training and reply.feedback['parent'] == parent for row, reply in samples)
        expected = ('t0', 't1') if index == 0 else ('t2', 't3')
        assert tuple(row.id for row, _ in samples) == expected
        proposed = 'repair-' + samples[0][1].feedback['diagnosis']
        proposals.append((parent, proposed))
        return proposed

    assert select_sequential_field_rewrites('start', training, validation, evaluate, schedule, propose,
                                             rounds=2, minibatch_size=2, metric_limit=limit) == winner
    assert proposals == [('start', 'repair-first'), ('repair-first', 'repair-second')][:generations]
    assert len(reads) == len(set(reads)) and len(reads) <= limit


def test_stateful_proposer_runs_on_a_perfect_training_batch():
    training, validation = (Row('train', 'task', fields=1),), (Row('validation', 'task', fields=1),)
    proposed = []

    def evaluate(prompt, row):
        assert prompt == 'start'
        passed = row.id == 'train'
        return Observation(passed, {}, int(passed))

    def propose(index, parent, samples):
        assert samples[0][1].passed
        proposed.append(index)
        return parent

    selected = select_sequential_field_rewrites(
        'start', training, validation, evaluate, lambda *_: ('start', ('train',)), propose,
        rounds=2, minibatch_size=1, metric_limit=8,
    )
    assert selected == 'start' and proposed == [0, 1]


def test_exhausted_source_keeps_the_candidate_already_admitted_to_search():
    training = (Row('train', 'task', fields=1),)
    validation = tuple(Row(case, 'task', fields=1) for case in ('v0', 'v1'))
    checks, scheduled, proposed = [], [], []

    def exhausted(index, pool):
        checks.append((index, pool))
        return index == 1

    def schedule(index, pool, grades):
        scheduled.append(index)
        return 'start', ('train',)

    def propose(index, parent, samples):
        proposed.append(index)
        return 'repair'

    def evaluate(prompt, row):
        passed = prompt == 'repair'
        return Observation(passed, {}, int(passed))

    selected = select_sequential_field_rewrites(
        'start', training, validation, evaluate, schedule, propose,
        rounds=3, minibatch_size=1, metric_limit=12, proposals_exhausted=exhausted,
    )
    assert selected == 'repair'
    assert checks == [(0, ('start',)), (1, ('start', 'repair'))]
    assert scheduled == proposed == [0]


def test_empty_proposal_slot_keeps_the_schedule_without_charging_feedback():
    training = tuple(Row(case, 'task', fields=1) for case in ('t0', 't1', 't2'))
    validation = tuple(Row(case, 'task', fields=1) for case in ('v0', 'v1'))
    scheduled, proposed, quoted = [], [], []

    def schedule(index, pool, grades):
        parent = 'repair' if index == 2 else 'start'
        scheduled.append(parent)
        return parent, (training[index].id,)

    def propose(index, parent, samples):
        proposed.append(index)
        return 'repair' if index == 0 else 'final'

    def evaluate(prompt, row):
        assert row.id != 't1'
        passed = prompt == 'final' or (prompt == 'repair' and row.id in ('t0', 'v0'))
        return Observation(passed, {}, int(passed))

    def quote(index, parent):
        quoted.append(index)
        return 1

    budget = SequentialSearchBudget(20, 1, quote, lambda *_: 1)
    selected = select_sequential_field_rewrites(
        'start', training, validation, evaluate, schedule, propose,
        rounds=3, minibatch_size=1, metric_limit=12, price_budget=budget, observed_charge=lambda *_: 1,
        proposal_unavailable=lambda index, parent: index == 1 and parent == 'start',
    )
    assert selected == 'final'
    assert scheduled == ['start', 'start', 'repair']
    assert proposed == quoted == [0, 2]


@pytest.mark.parametrize(('limit', 'expected'), ((None, [0, 1, 2]), (0, [0]), (5, [0, 1]), (6, [0, 1, 2])))
def test_proposal_limit_reserves_the_quote_and_reuses_settled_headroom(limit, expected):
    train, valid = (Row('train', 'task', fields=1),), (Row('validation', 'task', fields=1),)
    proposed = []

    def propose(index, parent, samples):
        assert samples[0][0] == train[0]
        proposed.append(index)
        return parent

    budget = SequentialSearchBudget(20, 1, lambda index, _: 4 if index else 0,
                                    lambda index, *_: 2 if index else 0, proposal_limit=limit)
    result = select_sequential_field_rewrites(
        'start', train, valid, lambda *_: Observation(False, {}, 0), lambda *_: ('start', ('train',)), propose,
        rounds=3, minibatch_size=1, metric_limit=8, observed_charge=lambda *_: 1,
        reinvest_savings=True, price_budget=budget,
    )
    assert result == 'start' and proposed == expected


@pytest.mark.parametrize('limit', (-1, True, 21))
def test_proposal_limit_must_fit_the_search_limit(limit):
    with pytest.raises(ValueError, match='proposal limit'):
        SequentialSearchBudget(20, 1, lambda *_: 1, lambda *_: 1, proposal_limit=limit)


@pytest.mark.parametrize(('skip_after', 'winner', 'expected_slots'),
                         ((None, 'start', [0, 1, 2]), (2, 'repair', [0, 1, 3])))
def test_skip_keeps_supplied_slots_and_can_fund_a_later_reflection(skip_after, winner, expected_slots):
    training = (Row('pass', 'task', fields=1), Row('miss', 'task', fields=1))
    validation = (Row('validation', 'task', fields=1),)
    scheduled, proposed, settled = [], [], []
    reads = set()

    def evaluate(prompt, row):
        assert (prompt, row.id) not in reads
        reads.add((prompt, row.id))
        assert len(reads) + sum(settled) <= 7
        passed = prompt == 'repair' or row.id == 'pass'
        return Observation(passed, {}, int(passed))

    def schedule(index, pool, _grades):
        assert pool == ('start',)
        scheduled.append(index)
        return 'start', (('miss' if index == 3 else 'pass'),)

    def propose(index, parent, samples):
        proposed.append(index)
        assert samples[0][1].passed == (index < 3)
        return 'repair' if index == 3 else parent

    def quote(index, _parent):
        return (0, 0, 3, 2)[index]

    def settle(index, parent, _child):
        assert proposed[-1] == index
        settled.append(quote(index, parent))
        assert len(reads) + sum(settled) <= 7
        return settled[-1]

    selected = select_sequential_field_rewrites(
        'start', training, validation, evaluate, schedule, propose, rounds=4, minibatch_size=1,
        metric_limit=8, reinvest_savings=True, observed_charge=lambda *_: 1,
        price_budget=SequentialSearchBudget(7, 1, quote, settle), skip_perfect_after=skip_after,
    )
    assert selected == winner
    assert proposed == expected_slots
    assert scheduled == [0, 1, 2, 3]
    assert settled == ([0, 0, 3] if skip_after is None else [0, 0, 2])


@pytest.mark.parametrize(('reinvest', 'expected_calls', 'winner'), ((False, 1, 'start'), (True, 2, 'repair')))
def test_reinvests_saved_reads_without_dropping_the_validation_reserve(reinvest, expected_calls, winner):
    training = tuple(Row(f't{case}', 'task', fields=1) for case in range(4))
    validation = tuple(Row(f'v{case}', 'task', fields=1) for case in range(4))
    paid, proposals = [], []

    def evaluate(prompt, row):
        assert len(paid) < 13
        paid.append((prompt, row.id))
        passed = prompt == 'repair' or (prompt == 'start' and row.id in ('t0', 't1'))
        return Observation(passed, {}, int(passed))

    def propose(index, parent, samples):
        proposals.append((index, parent))
        assert tuple(reply.passed for _, reply in samples) == ((True, True), (True, False))[index]
        return ('rejected', 'repair')[index]

    def schedule(index, pool, _grades):
        assert pool == ('start',)
        return 'start', (('t0', 't1'), ('t1', 't2'))[index]

    selected = select_sequential_field_rewrites(
        'start', training, validation, evaluate, schedule, propose, rounds=2, minibatch_size=2,
        metric_limit=13, reinvest_savings=reinvest,
    )
    assert len(proposals) == expected_calls and selected == winner
    assert len(paid) == len(set(paid))
    assert any(prompt == 'rejected' for prompt, _ in paid) != reinvest


@pytest.mark.parametrize(('limit', 'expected_calls', 'winner'), ((14, 1, 'start'), (15, 2, 'repair')))
def test_funds_the_proposal_as_well_as_each_reserved_evaluation(limit, expected_calls, winner):
    training = tuple(Row(f't{case}', 'task', fields=1) for case in range(4))
    validation = tuple(Row(f'v{case}', 'task', fields=1) for case in range(4))
    paid, proposals, settled = [], [], []

    def evaluate(prompt, row):
        paid.append((prompt, row.id))
        assert len(paid) + len(settled) <= limit
        passed = prompt == 'repair' or (prompt == 'start' and row.id in ('t0', 't1'))
        return Observation(passed, {}, int(passed))

    def schedule(index, pool, _grades):
        assert pool == ('start',)
        return 'start', (('t0', 't1'), ('t1', 't2'))[index]

    def propose(index, parent, samples):
        proposals.append((index, parent))
        return ('rejected', 'repair')[index]

    def settle(index, parent, _child):
        assert (index, parent) == proposals[-1]
        settled.append(index)
        assert len(paid) + len(settled) <= limit
        return 1

    budget = SequentialSearchBudget(limit, 1, lambda *_: 1, settle)
    selected = select_sequential_field_rewrites(
        'start', training, validation, evaluate, schedule, propose, rounds=2, minibatch_size=2,
        metric_limit=13, reinvest_savings=True, price_budget=budget, observed_charge=lambda *_: 1,
    )
    assert selected == winner and len(proposals) == len(settled) == expected_calls


def test_stops_after_a_charge_exceeds_its_quote():
    training, validation = (Row('train', 'task', fields=1),), (Row('validation', 'task', fields=1),)
    reads = []

    def evaluate(prompt, row):
        reads.append((prompt, row.id))
        return Observation(False, {}, 0)

    budget = SequentialSearchBudget(10, 1, lambda *_: 1, lambda *_: 2)
    with pytest.raises(ValueError, match='within its quoted maximum'):
        select_sequential_field_rewrites(
            'start', training, validation, evaluate, lambda *_: ('start', ('train',)),
            lambda *_: 'rewrite', rounds=2, minibatch_size=1, metric_limit=8, reinvest_savings=True,
            observed_charge=lambda *_: 1, price_budget=budget,
        )
    assert reads == [('start', 'validation'), ('start', 'train')]
