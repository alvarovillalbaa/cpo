"""T2 fixtures for case pairing and cost-constrained control selection."""

from fractions import Fraction
from itertools import product

from benchmarks import prompteval_rotating_witness_case_evidence as audit


PRIMARY = audit.transfer.PRIMARY


def panel(candidate, control, *, decisions, cost):
    cases = dict.fromkeys(audit.POINTS, [0] * len(candidate))
    cases.update({audit.CANDIDATE: candidate, PRIMARY: control})
    costs = dict.fromkeys(audit.POINTS, cost + 1)
    costs.update({'retain-start': 0, audit.CANDIDATE: cost, PRIMARY: cost})
    return {'caseIds': list(range(len(candidate))), 'decisionsPerCase': decisions, 'cases': cases,
            'paidLookups': costs}


def test_both_resampling_schemes_keep_each_case_paired_across_arms():
    subjects = {'a': panel([1, 7, 0], [1, 7, 0], decisions=8, cost=5),
                'b': panel([4, 2], [4, 2], decisions=5, cost=8)}
    plan = {'seed': 7, 'draws': 128}
    for resample_subjects in (False, True):
        result = audit.resample(subjects, plan, resample_subjects=resample_subjects)
        assert result['comparisons'][PRIMARY] == {
            'interval95PercentagePoints': [0.0, 0.0], 'drawsHigher': 0, 'drawsEqual': 128, 'drawsLower': 0,
        }


def test_equal_subject_weighting_preserves_an_exact_tie_with_unequal_case_counts():
    subjects = {'a': panel([1, 1], [0, 0], decisions=3, cost=5),
                'b': panel([2, 2, 2], [4, 4, 4], decisions=6, cost=8)}
    result = audit.resample(subjects, {'seed': 4, 'draws': 64}, resample_subjects=False)
    assert result['comparisons'][PRIMARY]['drawsEqual'] == 64


def test_subject_specific_native_allocation_matches_exhaustive_budget_search():
    baseline = 'gepa-batched/80'
    subjects = {'a': panel([2, 4], [3, 4], decisions=4, cost=8),
                'b': panel([4, 6, 5], [4, 5, 5], decisions=6, cost=8),
                'c': panel([4, 5], [6, 6], decisions=8, cost=8)}
    for unit in subjects.values():
        unit['cases'][baseline] = [unit['decisionsPerCase'] // 2] * len(unit['caseIds'])
        unit['paidLookups'][baseline] = 4

    options = []
    ceiling = 18
    for methods in product(audit.NATIVE, repeat=len(subjects)):
        cost, score = 0, Fraction(0)
        for unit, arm in zip(subjects.values(), methods, strict=True):
            cost += unit['paidLookups'][arm]
            score += Fraction(sum(unit['cases'][arm]), len(unit['caseIds']) * unit['decisionsPerCase'])
        if cost <= ceiling:
            options.append((score / len(subjects), -cost))
    actual = audit.native_allocation(subjects, ceiling)
    assert (Fraction(actual['macroAccuracy']), -actual['paidLookups']) == max(options)
