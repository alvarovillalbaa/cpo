"""T2 checks for the fixed calibration and audit case split."""

import pytest

from benchmarks.quoted_schedule_checkpoint_transfer import split_cases


def test_split_keeps_original_case_ids_and_is_stable_under_reordering():
    held = (3, 17, 25, 81, 101)
    left, right = split_cases('task', held)
    assert (len(left), len(right)) == (2, 3)
    assert set(left).isdisjoint(right)
    assert set(left) | set(right) == set(held)
    assert split_cases('task', held[::-1]) == (left, right)


@pytest.mark.parametrize('held', [(1,), (1, 1, 2)])
def test_split_rejects_missing_or_duplicate_cases(held):
    with pytest.raises(ValueError, match='distinct original holdout cases'):
        split_cases('task', held)
