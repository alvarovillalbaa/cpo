"""T2 tests for the rotating-witness cycle using scripted binary grades."""

import pytest

from cpo import Observation, Row
from cpo.rotating_witness import run_rotating_witness_cycle


VALIDATION = (Row('pass', 'task'), Row('miss', 'task'), Row('tie', 'task'))
QUALIFICATION = (Row('qualify-1', 'task'), Row('qualify-2', 'task'))


def run(outcomes, *, validation=VALIDATION, qualification_rows=QUALIFICATION, candidates=('first', 'second'),
        metric_limit=12, seed=0, **options):
    search_calls = []
    qualification_calls = []

    def evaluate(prompt, row):
        search_calls.append((prompt, row.id))
        return Observation(row.id in outcomes[prompt], {})

    def qualify(prompt, row, repeat):
        qualification_calls.append((prompt, row.id, repeat))
        return row.id in outcomes[prompt]

    result = run_rotating_witness_cycle('old', candidates, validation, qualification_rows, evaluate,
                                        qualify=qualify, metric_limit=metric_limit, seed=seed, **options)
    assert result.search.evaluations == len(search_calls)
    assert len(set(search_calls)) == len(search_calls) <= metric_limit
    assert result.qualification_evaluations == len(qualification_calls)
    return result, search_calls, qualification_calls


def test_rotation_and_third_row_rank_two_then_qualify_only_the_winner():
    outcomes = {'old': {'pass'}, 'first': {'pass', 'miss'},
                'second': {'pass', 'miss', 'tie', 'qualify-1', 'qualify-2'}}
    result, search, qualification = run(outcomes, metric_limit=9)
    assert result.promoted and result.prompt == 'second'
    assert search == [('old', 'pass'), ('old', 'tie'), ('first', 'tie'), ('second', 'tie'), ('second', 'pass')]
    assert {prompt for prompt, _, _ in qualification} == {'old', 'second'}
    assert {row for _, row, _ in qualification} <= {'qualify-1', 'qualify-2'}

    result, search, qualification = run(outcomes, metric_limit=8, seed=5)
    assert result.promoted and result.prompt == 'second'
    assert search == [('old', 'pass'), ('old', 'miss'), ('first', 'miss'), ('first', 'pass'),
                      ('second', 'miss'), ('second', 'pass'), ('first', 'tie'), ('second', 'tie')]
    assert {prompt for prompt, _, _ in qualification} == {'old', 'second'}


def test_tight_budget_keeps_first_eligible_candidate_and_retains_on_undecided_qualification():
    outcomes = {'old': {'pass'}, 'first': {'pass', 'miss', 'qualify-1', 'qualify-2'},
                'second': {'pass', 'miss', 'tie', 'qualify-1', 'qualify-2'}}
    result, search, qualification = run(outcomes, metric_limit=7, qualification_limit=1, seed=5)
    assert result.search.prompt == 'first' and len(search) == 6
    assert result.prompt == 'old' and result.qualification.status == 'undecided'
    assert len(qualification) == 1


def test_critical_validation_falls_back_to_the_safe_finalist_within_the_cap():
    rows = (*VALIDATION, Row('critical', 'task', critical=True))
    outcomes = {'old': {'pass', 'critical'}, 'first': {'pass', 'miss', 'tie'},
                'second': {'pass', 'miss', 'critical', 'qualify-1', 'qualify-2'}}
    result, search, _ = run(outcomes, validation=rows, metric_limit=11, seed=9)
    assert result.prompt == 'second' and result.promoted
    assert search[-3:] == [('old', 'critical'), ('first', 'critical'), ('second', 'critical')]
    assert len(search) == 11

    result, _, qualification = run(outcomes, validation=rows, metric_limit=10, seed=9)
    assert result.prompt == 'old' and not qualification


def test_qualification_rejects_critical_and_family_regressions():
    outcomes = {'old': {'pass', 'qualify-1'}, 'first': {'pass', 'miss', 'qualify-2', 'bonus'}}
    for row in (Row('qualify-1', 'task', critical=True), Row('qualify-1', 'protected')):
        result, _, qualification = run(outcomes, candidates=('first',), seed=5,
                                       qualification_rows=(row, QUALIFICATION[1], Row('bonus', 'task')))
        assert result.qualification.status == 'rejected' and result.prompt == 'old'
        assert qualification


@pytest.mark.parametrize('options', [{'metric_limit': -1}, {'qualification_limit': -1}, {'repeats': False},
                                     {'candidates': ('first', 'first')}, {'qualification_rows': VALIDATION}])
def test_invalid_configuration_fails_before_callbacks(options):
    with pytest.raises(ValueError):
        run({}, **options)


def test_zero_cap_and_empty_candidates_skip_both_callbacks():
    for options in ({'metric_limit': 0}, {'candidates': ()}):
        result, search, qualification = run({}, **options)
        assert result.prompt == 'old' and not search and not qualification
