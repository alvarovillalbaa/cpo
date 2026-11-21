from collections import Counter
from unittest.mock import patch

import pytest

from benchmarks import witness_cached_gepa_evidence as evidence
from cpo._contract import digest


def test_paired_draws_reselect_using_the_sampled_subject_budget():
    candidate, start = evidence.replay.CANDIDATE, evidence.replay.START
    left, right = 'gepa-sequential', 'gepa-batched'
    groups = {
        'left': {'caseIds': (10, 11), 'decisionsPerCase': 1,
                 'paidLookups': Counter({candidate: 3, left: 4, right: 2}),
                 'cases': {candidate: [1, 1], start: [0, 0], left: [1, 1], right: [1, 0]}},
        'right': {'caseIds': (20, 21), 'decisionsPerCase': 1,
                  'paidLookups': Counter({candidate: 3, left: 2, right: 4}),
                  'cases': {candidate: [1, 1], start: [0, 0], left: [1, 0], right: [1, 1]}},
    }
    result = evidence.summarize(groups, (left, right), {'draws': 128, 'seed': 42})
    draws = result['pairedResampling']['subjectsAndCases']
    assert draws['affordableSelections'][left] > 0
    assert draws['affordableSelections'][right] > 0
    assert sum(draws['affordableSelections'].values()) == 128
    assert result['totals'][candidate]['macroAccuracy'] == '1'
    assert result['totals'][candidate]['paidLookups'] == 6
    assert draws['comparisons']['best-affordable-gepa']['drawsLower'] == 0


def test_panel_uses_physical_case_order_and_refuses_a_different_native_trace():
    native, start = 'gepa-sequential', evidence.replay.START
    route = {'traceSha256': 'frozen-trace', 'holdoutPasses': 1, 'paidLookups': 2}
    retained = {native: route, start: {'holdoutPasses': 0, 'paidLookups': 0}}
    panel = {'caseIDs': ['second', 'first']}

    def measure(original, _plan, _inputs, _expected, _groups):
        assert original['caseOrderSha256'] == digest(panel['caseIDs'])
        return 'subject/model', {**retained, native: {**route, 'traceSha256': 'changed-trace'}}

    with patch.object(evidence.replay, 'measure_panel', measure):
        with pytest.raises(ValueError, match='Native GEPA replay differed'):
            evidence.measure({}, [panel], {'subject/model': retained}, {native: {}}, 16)
        with pytest.raises(ValueError, match='unique'):
            evidence.measure({}, [{'caseIDs': ['repeat', 'repeat']}], {}, {}, 16)
