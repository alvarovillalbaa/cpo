import pytest

from benchmarks import grounded_witness_halving_futility as original, witness_warehouse_confirmation as trial
from cpo._contract import digest


@pytest.fixture(scope='module')
def bound(tmp_path_factory):
    development = tmp_path_factory.mktemp('warehouse-confirmation') / 'development'
    groups, plan, _ = original.prepare()
    original.run(digest(plan), development, original.fixture_responder(groups, 'qualifying'), delivery='fixture')
    return development, trial.prepare(development)


@pytest.mark.parametrize(('profile', 'comparative', 'absolute', 'qualified'), (
    ('qualifying', True, 'qualified', True),
    ('single-miss', True, 'qualified', True),
    ('shared-rule-error', True, 'rejected', False),
    ('faulted-scoring', False, 'unmeasured', False),
))
def test_gate_and_exact_replay(tmp_path, bound, profile, comparative, absolute, qualified):
    development, (groups, plan, _, samples) = bound
    inherited = original.prepare(development)[1]
    assert plan['requestCeiling'] == inherited['requestCeiling'] == len(samples) == 128
    assert plan['parentConfirmationPlanSha256'] == digest(inherited)
    assert plan['developmentArchiveSha256'] == inherited['developmentArchiveSha256']
    assert plan['gate'] == inherited['gate']
    source = trial.archive_bytes(development)
    archive = tmp_path / 'archive'
    result = trial.run(digest(plan), archive, trial.fixture(groups, plan, profile), development=development)
    assert trial.replay(archive, tmp_path / 'replayed', development=development) == result
    assert trial.archive_bytes(development) == source
    assert (result['comparativeQualified'], result['absoluteVerdict']['status'], result['qualified']) == (
        comparative, absolute, qualified)
    if profile in ('shared-rule-error', 'single-miss'):
        first = plan['absoluteGate']['warehouseCaseIds'][0]
        assert result['absoluteVerdict']['passesByCase'][first] == (profile == 'single-miss')
        assert result['absoluteVerdict']['failedCases'] == ([first] if profile == 'shared-rule-error' else [])
    if profile == 'faulted-scoring':
        assert 'holdout' not in result
        assert result['scoring']['scoredRequests'] < plan['requestCeiling']
    else:
        assert result['scoring']['scoredRequests'] == plan['requestCeiling']


def test_wrong_seal_or_changed_archive_rejected(tmp_path, bound):
    development, (groups, plan, _, _) = bound
    respond = trial.fixture(groups, plan, 'qualifying')
    invalid = tmp_path / 'invalid'
    with pytest.raises(ValueError, match='current seal'):
        trial.run('0' * 64, invalid, respond, development=development)
    assert not invalid.exists()
    archive = tmp_path / 'archive'
    trial.run(digest(plan), archive, respond, development=development)
    path = archive / 'result.json'
    path.write_bytes(path.read_bytes().replace(b'"qualified": true', b'"qualified": false'))
    with pytest.raises(ValueError, match='differs from exact replay'):
        trial.replay(archive, tmp_path / 'replayed', development=development)
