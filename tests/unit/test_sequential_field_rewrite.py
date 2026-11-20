"""Verify feedback-driven generations and the native sequential reserve."""

import pytest

from cpo import Observation, Row
from cpo.sequential_field_rewrite import select_sequential_field_rewrites


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
