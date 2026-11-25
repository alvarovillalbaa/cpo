import json
from shutil import copytree

import pytest

from benchmarks import first_gain_bound_confirmation as study
from cpo._contract import digest


@pytest.fixture(scope='module')
def development(tmp_path_factory):
    return study.qualifying_development(tmp_path_factory.mktemp('development'))


def test_bound_exact_replay_preserves_all_regimes(development, tmp_path):
    plan, panel, samples, _ = study.bind(development)
    assert plan['logicalGrades'] == 576
    assert plan['scheduledRequests'] == 576
    out = tmp_path / 'shared-fault'
    result = study.execute(digest(plan), development, out, study.fixture(plan, panel, samples, 'shared-rule-error'))
    assert result['pairedGateMet']
    assert not result['qualified']
    assert result['failedRegimeCases']['warehouse'] == [panel['warehouse'][0]['id']]
    assert study.replay(development, out, tmp_path / 'replay') == result


def test_share_equal_prompt_only_within_a_case_and_repeat(development):
    prior = json.loads((development / 'result.json').read_bytes())
    plan, panel, tasks = study.specification.prepare()
    a, b = study.development.CONTROLS[:2]
    prior['selected']['ticket'][b] = prior['selected']['ticket'][a]
    samples = study.schedule(panel, tasks, prior['selected'], plan['repeats'])
    shared = [sample for sample in samples if len(sample.arms) == 2]
    assert len(samples) == 560
    assert len(shared) == 16
    assert all(sample.request['task'] == 'ticket' and set(sample.arms) == {a, b} for sample in shared)


def test_missing_failed_and_falsified_development_cannot_bind(development, tmp_path):
    with pytest.raises(ValueError, match='complete development'):
        study.bind(tmp_path / 'missing')
    failed = development.parent / 'unqualified'
    original = study.snapshot(failed, study.DEVELOPMENT_FILES)
    with pytest.raises(ValueError, match='qualifying development'):
        study.bind(failed)
    assert study.snapshot(failed, study.DEVELOPMENT_FILES) == original
    copytree(failed, tmp_path / 'falsified')
    result = tmp_path / 'falsified/result.json'
    body = json.loads(result.read_bytes())
    result.write_text(json.dumps({**body, 'qualifiedOnBothMeasures': True}))
    with pytest.raises(ValueError, match='differs from its exact replay'):
        study.bind(tmp_path / 'falsified')


def test_model_manifest_stale_seal_and_live_path_are_refused(development, tmp_path):
    model = tmp_path / 'model'
    copytree(development, model)
    manifest = model / 'plan.json'
    manifest.write_text(json.dumps({**json.loads(manifest.read_bytes()), 'delivery': 'model'}))
    with pytest.raises(ValueError, match='fixture archive'):
        study.bind(model)
    seal = digest(study.bind(development)[0])

    def unexpected(_):
        pytest.fail('A rejected launch must stop before scoring')

    for selected, path in (('stale', tmp_path / 'stale'), (seal, tmp_path / 'live-cpo-luna-guard')):
        with pytest.raises(ValueError, match='fresh isolated fixture'):
            study.execute(selected, development, path, unexpected)
        assert not path.exists()


def test_replay_detects_an_altered_request(development, tmp_path):
    plan, panel, samples, _ = study.bind(development)
    out = tmp_path / 'altered'
    result = study.execute(digest(plan), development, out,
                           study.fixture(plan, panel, samples, 'shared-single-miss'))
    assert result['qualified']
    wire = out / 'wire.jsonl'
    first, remainder = wire.read_bytes().split(b'\n', 1)
    body = json.loads(first)
    body['request']['repeat'] += 1
    wire.write_bytes(json.dumps(body).encode() + b'\n' + remainder)
    target = tmp_path / 'replay'
    with pytest.raises(ValueError, match='differs from exact replay'):
        study.replay(development, out, target)
    assert not (target / 'result.json').exists()
