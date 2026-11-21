"""T2 checks for one-admission fallback eligibility and lookup accounting."""

import pytest

from benchmarks import promptolution_witness_fallback as fallback


def trial(prompt, decisions, search, proof=()):
    counts = {'admissions': sum(x != 'no-nominee' for x in decisions), 'occupiedCycles': len(decisions),
              'promotions': decisions.count('promoted'), 'searchLookups': len(search),
              'admissionLookups': len(proof), 'paidLookups': len(search) + len(proof)}
    return prompt, counts, {'selected': prompt, 'decisions': decisions, 'search': search, 'admission': proof}


def test_failed_proof_spends_the_only_admission():
    original = trial('start', ['rejected'], [], [(('start', 3), True)])

    def forbidden():
        raise AssertionError('Fallback was called after a rejected admission')

    assert fallback.combine(original, forbidden) == original


def test_fallback_pays_once_for_shared_search_observations():
    original = trial('start', ['no-nominee'], [(('start', 1), False)])
    reserve = trial('other', ['promoted'], [(('start', 1), False), (('other', 1), True)], [(('start', 3), False)])
    selected, counts, trace = fallback.combine(original, lambda: reserve)
    assert selected == 'other'
    assert counts['admissions'] == counts['promotions'] == 1
    assert counts['searchLookups'] == 2 and counts['paidLookups'] == 3
    assert trace['reusedSearchLookups'] == 1
    assert trace['witnessDecisions'] == ['no-nominee']


def test_fallback_rejects_a_changed_paid_grade():
    original = trial('start', ['no-nominee'], [(('start', 1), False)])
    bad = trial('start', ['no-nominee'], [(('start', 1), True)])
    with pytest.raises(ValueError, match='immutable search grades'):
        fallback.combine(original, lambda: bad)
