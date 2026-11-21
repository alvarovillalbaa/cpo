from collections import Counter
from itertools import product

import pytest

from benchmarks.grounded_panel_evidence import assess, exact_tail, sign_flip_distribution


def test_exact_weighted_case_swaps_match_enumeration():
    for buckets in product(range(4), repeat=2):
        weights = [1] * buckets[0] + [2] * buckets[1]
        brute = Counter(sum(weight * sign for weight, sign in zip(weights, signs, strict=True))
                        for signs in product((-1, 1), repeat=len(weights)))
        assert sign_flip_distribution(weights) == brute
    assert exact_tail([2, 2, 0]) == {'tailAssignments': 1, 'totalAssignments': 4, 'oneSidedP': 0.25}
    assert exact_tail([1] * 5)['oneSidedP'] == 0.03125
    assert exact_tail([0, 0])['oneSidedP'] == 1.0


def rows():
    return [
        {'id': 'a', 'repeat': 0, 'critical': True,
         'passes': {'initial': False, 'cpo': True, 'sequential': False, 'batched': False}},
        {'id': 'a', 'repeat': 1, 'critical': True,
         'passes': {'initial': True, 'cpo': False, 'sequential': False, 'batched': True}},
    ]


def test_reports_case_ties_and_uncompensated_critical_replies_separately():
    result = assess({'task': rows()}, {'task': {'a': True}}, repeats=2, controls=('sequential', 'batched'))
    assert result['cases'] == 1 and result['repliesPerCasePerArm'] == 2
    seq, batched = (result['comparisons'][arm] for arm in ('sequential', 'batched'))
    assert seq['improvedCases'] == 1 and seq['caseSignFlip']['oneSidedP'] == 0.5
    assert batched['tiedCases'] == 1 and batched['matchedCriticalLosses'] == 1
    assert result['jointSuperiorityP'] == 1.0


@pytest.mark.parametrize('edit', ('missing', 'duplicate', 'other-case', 'critical', 'unknown-pass', 'missing-arm'))
def test_rejects_incomplete_or_different_sealed_cells(edit):
    panel = rows()
    if edit == 'missing':
        panel.pop()
    elif edit == 'duplicate':
        panel.append(panel[0])
    elif edit == 'other-case':
        panel[0]['id'] = 'b'
    elif edit == 'critical':
        panel[0]['critical'] = False
    elif edit == 'unknown-pass':
        panel[0]['passes']['cpo'] = None
    else:
        del panel[0]['passes']['batched']
    with pytest.raises(ValueError, match='complete matched panel|sealed case'):
        assess({'task': panel}, {'task': {'a': True}}, repeats=2, controls=('sequential', 'batched'))
