"""T2 check for common prices derived from measured lookup totals."""

import pytest

from benchmarks.recorded_math_router_frontier import anchor_budgets


def test_anchor_budgets_use_integer_prices_and_reject_inverted_anchors():
    assert anchor_budgets(411, 1016) == {
        'router-price': 411,
        'midpoint-price': 713,
        'strict-price': 1016,
    }
    with pytest.raises(ValueError):
        anchor_budgets(1016, 411)
