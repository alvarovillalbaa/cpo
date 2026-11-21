import pytest

from benchmarks import promptolution_paid_anchor_transfer as replay


def test_fallback_leaves_a_rejected_witness_proof_and_its_charges_intact():
    witness = (replay.episode.START, {'admissions': 1, 'promotions': 0, 'paidLookups': 12},
               {'decisions': ['rejected']})

    assert replay.extend(witness, {}, [], 1, replay.CANDIDATE, set()) is witness


def test_anchors_and_equal_cap_halving_respect_the_same_independent_proof():
    start = replay.episode.START
    witness = (start, {'admissions': 0, 'paidLookups': 1, 'searchLookups': 1, 'occupiedCycles': 1},
               {'search': [((start, 0), False)], 'admission': [], 'decisions': ['no-nominee']})
    layouts = [(('better', 'worse'), [0, 1, 2, 3], [4], [5, 6])]
    matrix = {start: '00000000', 'better': '11110110', 'worse': '00000110'}

    for method in (replay.CANDIDATE, replay.MATCHED):
        winner, cost, trace = replay.extend(witness, matrix, layouts, 9, method, {7})

        assert winner == 'better'
        assert 0 <= cost['fallbackSearchLookups'] <= replay.CAP
        assert cost['admissions'] == cost['promotions'] == 1
        assert cost['occupiedCycles'] == 2
        assert cost['paidLookups'] == len(trace['search']) + len(trace['admission'])
        assert set(prompt for (prompt, _), _ in trace['admission']) == {start, 'better'}
        assert all(case in {5, 6} for (_, case), _ in trace['admission'])

    with pytest.raises(ValueError, match='preserve the independent cases'):
        replay.extend(witness, matrix, layouts, 9, replay.CANDIDATE, {1, 7})
