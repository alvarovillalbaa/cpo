import pytest

from cpo import Observation, Row
from cpo.pool import PoolResult, select_pool
from cpo.two_witness_pool import select_two_witness_pool


ROWS = (Row('miss', 'task'), Row('protected', 'task', True), Row('last', 'task'))


def test_both_witnesses_are_considered_before_cutting_the_roster():
    roster = ('original', 'early', 'middle', 'late')
    grades = {'original': {'protected'}, 'early': {'miss', 'last'}, 'middle': {'miss'},
              'late': {'miss', 'protected'}}
    called = []

    def evaluate(prompt, row):
        called.append((prompt, row.id))
        return Observation(row.id in grades[prompt], {})

    result = select_two_witness_pool(roster, ROWS, evaluate, metric_limit=11)
    assert result == PoolResult('late', 2, len(called))
    assert len(called) == len(set(called)) <= 11
    assert ('early', 'last') not in called


def test_pruning_skips_late_second_witnesses_and_reuses_the_finalists_paid_replies():
    roster = ('original', 'a', 'b', 'c', 'd')
    calls = []

    def evaluate(prompt, row):
        key = prompt, row.id
        assert key not in calls
        calls.append(key)
        return Observation(prompt != 'original' or row.critical, {})

    result = select_two_witness_pool(roster, ROWS, evaluate, metric_limit=13)
    assert result == PoolResult('a', 3, 10)
    assert ('c', 'protected') not in calls
    assert ('d', 'protected') not in calls
    assert len(calls) == result.evaluations


def test_small_budget_uses_the_exact_bounded_pool():
    roster = ('original', 'a', 'b', 'c')

    def evaluate(prompt, row):
        return Observation(prompt == 'a' or row.critical, {})

    expected = select_pool(roster, ROWS, evaluate, metric_limit=6, adaptive_rejection=True)
    assert select_two_witness_pool(roster, ROWS, evaluate, metric_limit=6) == expected == PoolResult('a', 3, 6)


def test_bad_budget_or_duplicate_rows_are_rejected_before_any_callback():
    def evaluate(*args):
        pytest.fail('Invalid input reached the evaluator')

    with pytest.raises(ValueError, match='fund|cover'):
        select_two_witness_pool(('original', 'a'), ROWS, evaluate, metric_limit=2)
    with pytest.raises(ValueError, match='distinct'):
        select_two_witness_pool(('original', 'a'), (*ROWS, ROWS[0]), evaluate, metric_limit=6)
