"""T2 checks for prospective fallback, unchanged control paths, and confirmation binding."""

import pytest

from benchmarks import grounded, grounded_witness_episode as original, grounded_witness_halving as study
from benchmarks.grounded_witness_halving_fixture import RECOVERY_TASK, responder


def test_fallback_uses_one_proof_and_preserves_original_controls(tmp_path):
    pytest.importorskip('gepa')
    tasks, plan, _ = study.prepare()
    assert plan['parentPlanSha256'] == study.PARENT_SEAL and plan['requestCeiling'] == 3612
    mock = responder(tasks, 'qualifying')
    previous = original.run(study.PARENT_SEAL, tmp_path / 'original', mock, delivery='fixture')
    directory = tmp_path / 'development'
    result = study.run(study.digest(plan), directory, mock, delivery='fixture')
    assert result['qualifiedOnBothMeasures']
    for task in tasks:
        for arm in original.ARMS:
            assert result['selected'][task][arm] == previous['selected'][task][arm]
            assert result['admissions'][task][arm] == previous['admissions'][task][arm]
    for prices, recorded in zip(result['searchCosts'].values(), previous['searchCosts'].values(), strict=True):
        assert {arm: prices[arm] for arm in original.ARMS} == recorded

    recovery = result['admissions'][RECOVERY_TASK][study.CANDIDATE]
    assert all(step['admission'] == 'no-nominee' for step in recovery['witness'])
    assert [step['admission'] for step in recovery['fallback']] == ['promoted']
    assert result['additionalValidationUses'][RECOVERY_TASK][study.CANDIDATE] == 2
    assert study.replay(directory, tmp_path / 'development-replay') == result

    _, bound, _ = study.prepare(directory)
    assert bound['physicalLimitsByRole'] == {'qualification': 128}
    confirmation = tmp_path / 'confirmation'
    with pytest.raises(ValueError, match='matching delivery'):
        study.run(study.digest(bound), confirmation, mock, delivery='model', development=directory)
    confirmed = study.run(study.digest(bound), confirmation, mock, delivery='fixture', development=directory)
    assert confirmed['selected'] == result['selected'] and confirmed['qualifiedOnBothMeasures']
    assert confirmed['physicalCallsByRole'] == {'qualification': 128}
    assert study.replay(confirmation, tmp_path / 'confirmation-replay', development=directory) == confirmed


def test_rejection_retains_incumbent_and_blocks_fallback_and_confirmation(tmp_path):
    pytest.importorskip('gepa')
    tasks, plan, _ = study.prepare()
    directory = tmp_path / 'rejected'
    result = study.run(study.digest(plan), directory, responder(tasks, 'rejected'), delivery='fixture')
    assert not result['qualifiedOnBothMeasures']
    for task in tasks:
        log = result['admissions'][task][study.CANDIDATE]
        assert [step['admission'] for step in log['witness']] == ['rejected']
        assert not log['fallback']
        assert result['selected'][task][study.CANDIDATE] == grounded.BASELINE
    with pytest.raises(ValueError, match='exact, qualifying'):
        study.prepare(directory)


def test_search_cannot_start_proof_after_hitting_its_new_validation_cap():
    groups = original.cohorts()[RECOVERY_TASK]
    evaluated = []

    def evaluate(prompt, case):
        evaluated.append((prompt, case))
        return False

    def forbidden(*_):
        pytest.fail('An unfinished fallback tried to start proof')

    roster = [(('first draft', 'second draft'), 1)] * original.CYCLES
    selected, log, used = study.run_halving(grounded.BASELINE, RECOVERY_TASK, roster, groups, evaluate, forbidden,
                                             metric_limit=1, logical_limit=8)
    assert selected == grounded.BASELINE
    assert [step['admission'] for step in log] == ['capped']
    assert len(evaluated) == used == 1
