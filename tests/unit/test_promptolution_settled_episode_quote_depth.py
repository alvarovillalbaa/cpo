import pytest

from benchmarks import promptolution_settled_episode_quote_depth as variant
from cpo import Observation, Row
from cpo.feedback_episode import _FEEDBACK_RUNNERS


@pytest.mark.parametrize(('width', 'cap', 'halve', 'expected'), (
    (8, 18, False, 2),
    (4, 6, True, 1),
    (8, 9, True, 1),
    (8, 14, True, 2),
))
def test_preserves_original_funded_depth_with_two_challengers(width, cap, halve, expected):
    cases = tuple(Row(str(index), 'task') for index in range(6))

    def inspect(_incumbent, _candidates, rows, _evaluate, _cap):
        return rows

    actual = variant.preserve_depth(inspect, width, cap, halve, 'base', ('a', 'b'), cases, None, 19)
    assert actual == cases[:expected]


def test_a_critical_case_after_the_nominal_depth_stays_considered():
    cases = tuple(Row(str(index), 'task', critical=index == 5) for index in range(6))

    def inspect(_incumbent, _candidates, rows, _evaluate, _cap):
        return rows

    actual = variant.preserve_depth(inspect, 8, 18, False, 'base', ('a', 'b'), cases, None, 19)
    assert actual == cases


@pytest.mark.parametrize('schedule', tuple(variant.RUNNERS))
@pytest.mark.parametrize('opening_miss', (0, 1, 2, 3))
def test_full_rosters_retain_exact_original_transitions(schedule, opening_miss):
    pool = tuple(f'candidate-{i}' for i in range(8))
    search = tuple(Row(str(i), 'task') for i in range(6))
    qualification = tuple(Row(str(i + 6), 'task') for i in range(4))

    def play(runner):
        paid = []

        def evaluate(prompt, row):
            paid.append(('validation', prompt, row.id))
            return Observation(prompt != 'base' and int(row.id) % 3 != 2, {})

        def qualify(prompt, row, repeat):
            paid.append(('qualification', prompt, row.id, repeat))
            return prompt != 'base' or int(row.id) - 6 != opening_miss

        result = runner('base', pool, search, qualification, evaluate, metric_limit=19, qualify=qualify, seed=27)
        return result, paid

    assert play(variant.RUNNERS[schedule]) == play(_FEEDBACK_RUNNERS[schedule])
