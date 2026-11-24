"""T2 checks for disjoint calibration and hard-cap setting selection."""

import pytest

from benchmarks.recorded_math_budget_crossfit import RETAIN, partition, pick


def test_partition_keeps_each_case_in_one_fold_independent_of_input_order():
    cases = tuple(f'case-{i}' for i in range(9))
    first, second = partition('fixture', cases)
    assert (len(first), len(second)) == (4, 5)
    assert sorted((*first, *second)) == list(range(9))
    reverse_first, _ = partition('fixture', cases[::-1])
    assert {cases[i] for i in first} == {cases[::-1][i] for i in reverse_first}
    with pytest.raises(ValueError, match='unique identities'):
        partition('fixture', (*cases, cases[0]))


@pytest.mark.parametrize('cheaper,expensive', [
    ('routed/19', 'paired-certificate/20'),
    ('half:gepa-sequential-precheck/19/gain-1', 'full:gepa-batched-precheck/20/gain-1'),
    ('uniform/4/19', 'successive-halving/8/20'),
])
def test_selection_respects_the_configured_cap_even_if_realized_cost_is_lower(cheaper, expensive):
    totals = {cheaper: {'holdoutPasses': 4, 'paidLookups': 28},
              expensive: {'holdoutPasses': 5, 'paidLookups': 23},
              RETAIN: {'holdoutPasses': 3, 'paidLookups': 0}}
    assert pick(totals, (cheaper, expensive), 19, 6, 1)['setting'] == cheaper
    assert pick(totals, (cheaper, expensive), 20, 6, 1)['setting'] == expensive
    assert pick(totals, (cheaper, expensive), 18, 6, 1)['setting'] == RETAIN
