from copy import deepcopy

import pytest

from benchmarks import grounded_policy_regimes as policy, grounded_staged
from cpo._contract import digest


def test_sealed_confirmation_reuses_regimes_with_distinct_inputs():
    groups = grounded_staged.cohorts()
    assert digest(groups) == policy.ORIGINAL_DATA_SHA256
    original, stress = policy.audit(groups, policy.build_stress(groups))
    assert [row['rowsSeenBySplit']['train'] for row in original.values()] == [8, 8, 8]
    assert original['ticket']['topicAndChannel']['rowsWithPreviouslySeenRegime'] == 8
    assert stress['ticket']['rowsWithPreviouslySeenRegime'] == 6
    assert stress['ticket']['topicAndChannel']['rowsWithPreviouslySeenRegime'] == 0
    assert [stress[key]['rowsWithPreviouslySeenRegime'] for key in ('warehouse', 'outage')] == [0, 0]
    assert [stress[key]['distinctRegimes'] for key in ('warehouse', 'outage')] == [6, 8]


def test_stress_policy_covers_active_and_equal_caps_and_missing_evidence_override():
    groups = grounded_staged.cohorts()
    rows = policy.build_stress(groups)['outage']
    assert any(policy.regime('outage', row['input']) == (120, 'PLUS', 'POSTED', 'binding')
               and row['expected'] == {'credit': 17, 'review': True, 'reason': 'LONG'} for row in rows)
    assert any(policy.regime('outage', row['input']) == (120, 'STANDARD', 'MISSING', 'equal')
               and row['expected'] == {'credit': 24, 'review': True, 'reason': 'NEEDS_DOC'} for row in rows)


def test_stress_audit_rejects_a_reused_input_or_wrong_score():
    groups = grounded_staged.cohorts()
    stress = policy.build_stress(groups)
    changed = deepcopy(stress)
    changed['warehouse'][0]['input'] = groups['warehouse']['train'][0]['input']
    with pytest.raises(ValueError, match='distinct identities'):
        policy.audit(groups, changed)
    changed = deepcopy(stress)
    changed['outage'][0]['expected']['credit'] += 1
    with pytest.raises(ValueError, match='unchanged policy scorer'):
        policy.audit(groups, changed)
