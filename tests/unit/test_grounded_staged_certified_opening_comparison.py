"""Check certified opening validation through development and its bound panel."""

from hashlib import sha256

import pytest

from benchmarks import grounded_staged_certified_opening_comparison as certified
from benchmarks import grounded_staged_opening_dominance_comparison as dominance
from benchmarks import grounded_staged_fixture, grounded_staged_policy_comparison as full
from cpo._contract import digest


@pytest.mark.parametrize(('baseline_runner', 'candidate_runner', 'version', 'proof_source', 'entry_source'), (
    (full, certified, 3, 'cpo/opening_validation.py', 'grounded_staged_certified_opening_comparison.py'),
    (certified, dominance, 4, 'cpo/opening_dominance.py', 'grounded_staged_opening_dominance_comparison.py'),
))
def test_certificate_is_sealed_and_preserves_selections_and_confirmation(
        tmp_path, baseline_runner, candidate_runner, version, proof_source, entry_source):
    _, baseline, _ = baseline_runner.prepare()
    _, trial, _ = candidate_runner.prepare()
    assert trial['protocol'] == f'portable-grounded-staged-policy-comparison-v{version}'
    assert trial['corpusSha256'] == baseline['corpusSha256']
    assert trial['logicalLimitsByRole'] == baseline['logicalLimitsByRole']
    assert trial['gate'] == baseline['gate']
    for name in (proof_source, f'benchmarks/{entry_source}'):
        assert trial['sourceSha256'][name] == sha256((full.staged.ROOT / name).read_bytes()).hexdigest()

    baseline_path, development = tmp_path / 'baseline', tmp_path / 'development'
    fixture = grounded_staged_fixture.respond
    with pytest.raises(ValueError, match='current comparison seal'):
        candidate_runner.run(digest(baseline), development, lambda _: pytest.fail('Called responder'),
                             delivery='fixture')
    assert not development.exists()
    before = baseline_runner.run(digest(baseline), baseline_path, fixture, delivery='fixture')
    result = candidate_runner.run(digest(trial), development, fixture, delivery='fixture')
    assert result['admissionDecisions'] == before['admissionDecisions']
    assert result['selected'] == before['selected']
    assert result['holdout'] == before['holdout']
    assert result['searchCallsByArm']['opening-only'] <= before['searchCallsByArm']['opening-only']
    for arm in (name for name in candidate_runner.ARMS if name != 'opening-only'):
        assert result['searchCallsByArm'][arm] == before['searchCallsByArm'][arm]
    assert candidate_runner.replay(development, tmp_path / 'development-replay') == result

    with pytest.raises(ValueError, match='current comparison seal'):
        candidate_runner.prepare(baseline_path)
    _, bound, _ = candidate_runner.prepare(development)
    assert bound['protocol'] == trial['protocol'] + '-confirmation'
    assert bound['developmentPlanSha256'] == digest(trial)
    panel = tmp_path / 'panel'
    confirmation = candidate_runner.run(digest(bound), panel, fixture, development=development, delivery='fixture')
    assert confirmation['qualifyingInBothStages'] == ['cpo']
    assert candidate_runner.replay(panel, tmp_path / 'panel-replay', development=development) == confirmation
