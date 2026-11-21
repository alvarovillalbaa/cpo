from collections import Counter

import pytest

from benchmarks import recorded_calibrated_training_route as study


def test_strata_use_exact_gain_and_any_lost_incumbent_pass():
    incumbent = (1, 0, 0, 0)
    for challenger, bucket in (
            ((1, 1, 0, 0), 'one-clean'), ((0, 1, 1, 0), 'one-mixed'),
            ((1, 1, 1, 0), 'multiple-clean'), ((0, 1, 1, 1), 'multiple-mixed')):
        assert study.stratum(incumbent, challenger) == bucket
    with pytest.raises(ValueError, match='strictly improving'):
        study.stratum(incumbent, (0, 1, 0, 0))


def test_calibration_weights_families_equally_and_requires_support_in_each():
    evidence = {family: {bucket: Counter() for bucket in study.STRATA} for family in ('A', 'B', 'C')}
    for family, grades, delta in (('A', 800, 16), ('B', 400, -20), ('C', 20_000, 400)):
        evidence[family]['one-clean'].update(trials=8, heldoutGrades=grades, holdoutPassDelta=delta)
        evidence[family]['one-mixed'].update(trials=8, heldoutGrades=grades, holdoutPassDelta=abs(delta))
        evidence[family]['multiple-clean'].update(trials=7, heldoutGrades=grades, holdoutPassDelta=abs(delta))
    assert study.fit(evidence) == ('one-mixed',)


def test_a_fitted_route_only_vetoes_after_independent_qualification():
    cells = {prompt: tuple((score, None, False) for score in grades) for prompt, grades in {
        'start': (1, 1, 0, 0, 1, 0, 0, 0, 0, 0),
        'new': (0, 1, 0, 0, 1, 1, 0, 1, 0, 1),
    }.items()}
    cohorts = ([0, 1, 2, 3], [4, 5, 6], [7, 8], [9])
    args = (cells, 'start', ('new',), cohorts, 31, 10)
    before, original, prior_grades, bucket = study.run_trial(*args, ())
    after, revised, revised_grades, checked = study.run_trial(*args, ('one-clean',))
    assert bucket == checked == 'one-clean'
    assert original[2:4] == ('new', 'new') and prior_grades == (1,)
    assert revised[2:4] == ('new', 'start') and revised_grades == (0,)
    assert after['trainingChecks'] == after['trainingVetoes'] == 1
    assert after['paidLookups'] - before['paidLookups'] == after['trainingLookups']
    assert after['qualificationLookups'] == before['qualificationLookups']

    rejected = {**cells, 'new': (*cells['new'][:7], (0, None, False), *cells['new'][8:])}
    unqualified = (rejected, *args[1:])
    assert study.run_trial(*unqualified, study.STRATA) == study.run_trial(*unqualified, ())
