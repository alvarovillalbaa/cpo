from types import SimpleNamespace

import pytest

from benchmarks import witness_admission_retry as retry


LAYOUTS = [
    {'qualify': [0, 1], 'alternatives': ['1', '4']},
    {'qualify': [2, 3], 'alternatives': ['2']},
    {'qualify': [4, 5], 'alternatives': ['3']},
]
ROSTER = {'1': 0, '2': 1, '3': 2, '4': 0}
PLAN = {'minimumQualificationGain': 1, 'maximumExtensionRows': 1}
GRADES = {('2', 6): True, ('1', 6): True, ('3', 6): False}


def test_retries_with_full_unused_panel_and_remaining_budget():
    # Row 3 was never read, but it belongs to the rejected nominee's panel.
    first = SimpleNamespace(prompt='0', status='rejected', used_reserve=True,
                            observations=[SimpleNamespace(row_id=str(row)) for row in (0, 2, 2)])
    seen = []

    def grade(prompt, case):
        seen.append((prompt, case))
        return prompt == '1'

    decision = retry.try_retry(first, 6, '0', '2', [0], LAYOUTS, ROSTER, PLAN, GRADES, grade)

    assert decision == retry.Decision('1', 6, 'promoted', retry=True, retry_lookups=3)
    assert len(seen) == 3
    assert {case for _, case in seen} == {4, 5}


@pytest.mark.parametrize(('status', 'cap'), [('rejected', 5), ('undecided', 6), ('promoted', 6)])
def test_skips_retry_without_exact_rejection_and_enough_remaining_budget(status, cap):
    first = SimpleNamespace(prompt='0', status=status, used_reserve=True, observations=[None] * 3)

    def grade(_prompt, _case):
        pytest.fail('An ineligible retry read an admission case')

    assert retry.try_retry(first, cap, '0', '2', [0], LAYOUTS, ROSTER, PLAN, GRADES, grade) == (
        retry.Decision('0', 3, status))


def test_rival_ranking_ignores_unpaid_candidates_and_uses_layout_order_for_ties():
    tied = {**GRADES, ('3', 6): True}

    assert retry.ranked_rival(LAYOUTS, '2', tied) == '1'
    assert retry.ranked_rival(LAYOUTS, '2', {('2', 6): True}) is None
