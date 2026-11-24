"""T2 checks for task schedule promotion at an independent guard split."""

import pytest

from benchmarks.quoted_schedule_guarded_transfer import accept


@pytest.mark.parametrize('lower,task_spend,prefix_spend,expected', [
    (-1, 1, 20, False),
    (2, 21, 20, False),
    (0, 20, 20, False),
    (0, 19, 20, True),
    (2, 20, 20, True),
])
def test_switch_needs_nonnegative_paired_lower_bound_and_no_added_cost(lower, task_spend, prefix_spend, expected):
    assert accept(lower, task_spend, prefix_spend) is expected
