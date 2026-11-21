"""Exercise the admission limit through the public episode API."""

import pytest

from cpo import Observation, Row
from cpo.rotating_witness.episode import WitnessCycle, run_rotating_witness_episode


VALIDATION = (Row('validated lose', 'task'), Row('validated pass', 'task'))


def cycle(candidate, number):
    return WitnessCycle((candidate,), VALIDATION, (Row(f'qualification {number}', 'task'),), seed=number)


def test_rejected_first_attempt_skips_all_later_search():
    search, qualification = [], []

    def measure(prompt, row):
        search.append((prompt, row.id))
        return Observation(prompt != 'incumbent' or row.id == 'validated pass', {})

    def qualify(prompt, row, repeat):
        qualification.append((prompt, row.id, repeat))
        return False

    result = run_rotating_witness_episode('incumbent', (cycle('first', 1), cycle('second', 2)),
                                          measure, qualify=qualify, metric_limit=4)
    assert (result.prompt, result.admission_attempts, len(result.cycles)) == ('incumbent', 1, 1)
    assert result.cycles[0].qualification.status == 'rejected'
    assert {prompt for prompt, _ in search} == {'incumbent', 'first'}
    assert {row for _, row, _ in qualification} == {'qualification 1'}


def test_no_nomination_leaves_one_attempt_for_a_later_cycle():
    def measure(prompt, row):
        return Observation(prompt == 'winner' or row.id == 'validated pass', {})

    result = run_rotating_witness_episode('incumbent', (cycle('stall', 1), cycle('winner', 2), cycle('unread', 3)),
                                          measure, qualify=lambda prompt, *_: prompt == 'winner', metric_limit=4)
    assert (result.prompt, result.admission_attempts, len(result.cycles)) == ('winner', 1, 2)
    assert result.cycles[0].qualification is None
    assert result.cycles[1].promoted


@pytest.mark.parametrize('rows', [(VALIDATION[0],), (Row('qualification 1', 'task'),)])
def test_blocks_future_qualification_overlap_before_callbacks(rows):
    def unexpected(*_):
        pytest.fail('Overlap must be detected before evaluation')

    with pytest.raises(ValueError, match='qualification'):
        run_rotating_witness_episode('incumbent', (cycle('first', 1), WitnessCycle(('later',), VALIDATION, rows)),
                                      unexpected, qualify=unexpected, metric_limit=4)


def test_zero_budget_and_undecided_attempt_have_no_later_callbacks():
    def unexpected(*_):
        pytest.fail('No callback should run with a zero cap on its role')

    policy = (cycle('first', 1), cycle('later', 2))
    stopped = run_rotating_witness_episode('incumbent', policy, unexpected, qualify=unexpected,
                                           metric_limit=4, max_admissions=0)
    assert stopped.admission_attempts == 0 and not stopped.cycles
    result = run_rotating_witness_episode('incumbent', policy,
                                          lambda prompt, row: Observation(prompt == 'first' or row == VALIDATION[1], {}),
                                          qualify=unexpected, metric_limit=4, qualification_limit=0)
    assert result.admission_attempts == 1 and len(result.cycles) == 1
    assert result.cycles[0].qualification.status == 'undecided'
