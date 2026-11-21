"""T2 tests for the packaged paired opening on scripted replies."""

from itertools import product

import pytest

from benchmarks.recorded_rotating_witness_graph import opening_proof
from cpo import Observation, ProposalPair, Row
from cpo.family_qualification import certify_family_qualification
from cpo.paired_opening import run_paired_opening_cycle


PROMPTS = ('old', 'rewrite', 'repair')
OPENING = ProposalPair(*PROMPTS[1:])
VALIDATION = (Row('ordinary', 'task'), Row('critical', 'task', critical=True), Row('other', 'other'))
QUALIFICATION = (Row('qualification', 'task'),)


def evaluate_grades(grades, calls):
    def evaluate(prompt, row):
        calls.append((prompt, row.id))
        return Observation(grades[prompt, row.id], {})

    return evaluate


def test_package_matches_the_sealed_opening_proof_with_partial_and_full_budgets():
    keys = [(prompt, row.id) for prompt in PROMPTS for row in VALIDATION]
    for values in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, values, strict=True))
        for budget in (5, 7, 9):
            expected, actual = [], []
            reference, _ = opening_proof('old', PROMPTS[1:], VALIDATION, evaluate_grades(grades, expected),
                                         certify_family_qualification, cap=budget, seed=0, prioritize=False)
            result = run_paired_opening_cycle(
                'old', VALIDATION, QUALIFICATION, evaluate_grades(grades, actual), opening_pair=OPENING,
                metric_limit=budget, qualify=lambda *_: pytest.fail('The qualification cap is zero'),
                qualification_limit=0,
            )
            assert result.search == reference and actual == expected
            assert len(set(actual)) == len(actual) <= budget
            assert result.prompt == 'old'


def test_qualifies_only_the_first_proven_opening():
    grades = {(prompt, row.id): prompt in ('rewrite', 'repair') for prompt in PROMPTS for row in VALIDATION}
    seen, proof = [], []

    def qualify(prompt, row, repeat):
        proof.append((prompt, row.id, repeat))
        return prompt != 'rewrite'

    result = run_paired_opening_cycle(
        'old', VALIDATION, QUALIFICATION, evaluate_grades(grades, seen), opening_pair=OPENING,
        metric_limit=9, qualify=qualify,
    )
    assert result.search.prompt == 'rewrite'
    assert result.qualification.status == 'rejected' and result.prompt == 'old'
    assert all(prompt != 'repair' for prompt, _ in seen)
    assert {case for _, case, _ in proof} == {'qualification'}


def test_fallback_reuses_the_incumbent_and_protects_critical_validation_passes():
    passes = {'old': {'critical'}, 'rewrite': {'ordinary', 'other'}, 'repair': {'ordinary', 'critical', 'other'}}
    grades = {(prompt, row.id): row.id in passes[prompt] for prompt in PROMPTS for row in VALIDATION}
    calls = []
    result = run_paired_opening_cycle(
        'old', VALIDATION, QUALIFICATION, evaluate_grades(grades, calls), opening_pair=OPENING,
        metric_limit=9, qualify=lambda prompt, *_: prompt == 'repair',
    )
    assert result.promoted and result.prompt == 'repair'
    assert ('rewrite', 'critical') in calls
    assert calls.count(('old', 'critical')) == 1
    assert result.search.evaluations == len(calls)


def test_qualification_repeats_stop_at_their_own_cap():
    grades = {(prompt, row.id): prompt == 'rewrite' for prompt in PROMPTS for row in VALIDATION}
    proof = []

    def qualify(prompt, row, repeat):
        proof.append((prompt, row.id, repeat))
        return prompt == 'rewrite'

    result = run_paired_opening_cycle(
        'old', VALIDATION, QUALIFICATION, evaluate_grades(grades, []), opening_pair=OPENING,
        metric_limit=9, qualify=qualify, repeats=2, minimum_gain=2, qualification_limit=3,
    )
    assert result.search.prompt == 'rewrite'
    assert result.prompt == 'old' and result.qualification.status == 'undecided'
    assert result.qualification_evaluations == len(set(proof)) == 3


@pytest.mark.parametrize('options', [{'opening_pair': ProposalPair('old', 'rewrite')}, {'metric_limit': True},
                                     {'qualification_rows': VALIDATION}, {'repeats': 0}, {'qualification_limit': -1}])
def test_invalid_configuration_fails_before_dispatch(options):
    def unexpected(*_):
        pytest.fail('Malformed configurations must fail before dispatch')

    supplied = {'opening_pair': OPENING, 'metric_limit': 9, 'qualification_rows': QUALIFICATION, **options}
    with pytest.raises(ValueError):
        run_paired_opening_cycle('old', VALIDATION, evaluate=unexpected, qualify=unexpected, **supplied)
