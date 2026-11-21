"""Check that paid witness reuse respects admission and holdout boundaries."""

import pytest

from benchmarks import prompteval_retired_admission_witness as replay


def test_prefers_a_retired_pair_and_keeps_seeded_anchors_for_the_finalist():
    layout = {'seed': 13, 'validation': (10, 11, 12)}
    search = {('incumbent', 10): True, ('incumbent', 11): False}
    retired = {('incumbent', 20): True, ('incumbent', 21): False, ('other', 22): True}
    order, moved, cached = replay.witnesses('incumbent', layout, search, retired)
    assert cached is True
    assert order[:2] == [20, 21]
    assert set(order[2:]) == {10, 11, 12}
    assert moved == {20, 21}


def test_preserves_the_original_rotation_until_both_incumbent_grades_are_available():
    layout = {'seed': 81, 'validation': (10, 11, 12)}
    original = replay.witnesses('incumbent', layout, {}, {})
    assert replay.witnesses('incumbent', layout, {('incumbent', 10): True}, {('other', 20): False}) == original
    assert not original[1] and original[2] is False


def test_rejects_a_search_using_an_unobserved_admission_case(monkeypatch):
    layouts = ({'seed': 0, 'validation': (0, 1), 'train': (), 'qualify': (2,), 'alternatives': ('1',)},)
    cap = {'evaluationLookupLimit': 5}
    monkeypatch.setattr(replay, 'witnesses', lambda *_: ([2, 0, 1], {2}, True))
    with pytest.raises(ValueError, match='previously observed and retired'):
        replay.history_episode(('1001', '1111'), (3,), '0', layouts, cap, replay.RETIRED)


def test_admission_grades_are_reused_without_another_paid_read():
    layout = {'seed': 3, 'validation': (0, 1, 2), 'train': (), 'qualify': [3, 4, 5, 6], 'alternatives': ('1',)}
    later = {**layout, 'seed': 4, 'qualify': [7, 8, 9, 10], 'alternatives': ('2',)}
    plan = {'evaluationLookupLimit': 10, 'maximumExtensionRows': 1,
            'minimumQualificationGain': 1, 'qualificationPolicy': 'extend-ties'}
    matrix = ('100000000000', '111101100001', '111111100000')
    _, paid, _ = replay.history_episode(matrix, (11,), '0', (layout, later), plan, replay.RETIRED)
    assert paid['retiredWitnessCycles'] == 1
    assert paid['reusedAdmissionGrades'] == 2
    assert paid['newSearchLookupsOnRetiredCases'] > 0
    assert paid['paidLookups'] == paid['newSearchLookups'] + paid['qualificationLookups']
