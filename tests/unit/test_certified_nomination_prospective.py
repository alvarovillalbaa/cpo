from dataclasses import replace
import json
from shutil import copytree

import pytest

from benchmarks import certified_nomination_prospective as study
from cpo._contract import digest


@pytest.fixture
def archive(tmp_path):
    tasks, plan = study.prepare()
    out = tmp_path / 'fixture'
    result, audit = study.run_fixture(digest(plan), out)
    return tasks, plan, out, result, audit


def test_shared_narrow_rosters_and_full_holdouts_replay(archive, tmp_path):
    tasks, plan, source, result, audit = archive
    assert sum(plan['physicalLimitsByRole'].values()) == plan['requestCeiling'] == 2004
    assert result['physicalCallsByRole']['reflection'] == len(tasks) * plan['cycles'] == 9
    assert all(rosters == [2, 2, 2] for rosters in result['rosterSizes'].values())
    assert result['decisions']['ticket'][study.CERTIFIED][0]['schedule'] == 'successive-halving/4/6'
    assert result['decisions']['outage'][study.CERTIFIED][0]['schedule'] == 'uniform/8/18'
    assert audit['routingComparison']['validationLookupsSaved'] > 0
    assert audit['routingComparison']['differentValidationCharges'] > 0
    assert audit['holdoutRequests'] == result['physicalCallsByRole']['qualification']
    assert audit['providerRequests'] == 0
    for verdict in result['verdicts'].values():
        assert set(verdict['comparisons']) == {'initial', *study.CONTROLS}
    assert study.replay(source, tmp_path / 'replay') == (result, audit)


def test_a_final_prompt_mismatch_stops_before_any_holdout(tmp_path, monkeypatch):
    original = study.ROUTED_RUNNERS[study.CERTIFIED]

    def divergent(*args, **kwargs):
        return replace(original(*args, **kwargs), prompt='unpaired fixture prompt')

    monkeypatch.setitem(study.ROUTED_RUNNERS, study.CERTIFIED, divergent)
    _, plan = study.prepare()
    archive = tmp_path / 'divergent'
    with pytest.raises(ValueError, match='preserve the full routed decision'):
        study.run_fixture(digest(plan), archive)
    rows = [json.loads(line) for line in (archive / 'wire.jsonl').read_bytes().splitlines()]
    assert all(row.get('request', {}).get('role') != 'qualification' for row in rows)
    assert not (archive / 'result.json').exists()


def test_stale_seals_and_model_manifests_are_refused(archive, tmp_path):
    _, _, source, _, _ = archive
    output = tmp_path / 'refused'
    with pytest.raises(ValueError, match='sealed plan'):
        study.run_fixture('stale seal', output)

    model = tmp_path / 'model'
    copytree(source, model)
    path = model / 'plan.json'
    plan = json.loads(path.read_bytes())
    path.write_text(json.dumps({**plan, 'delivery': 'model'}))
    with pytest.raises(ValueError, match='Only fixture archives'):
        study.replay(model, output)
    assert not output.exists()


def test_altered_validation_request_breaks_replay(archive, tmp_path):
    _, _, source, _, _ = archive
    damaged = tmp_path / 'damaged'
    copytree(source, damaged)
    wire = damaged / 'wire.jsonl'
    events = [json.loads(line) for line in wire.read_bytes().splitlines()]
    validation = next(event for event in events if event.get('request', {}).get('role') == 'evaluation')
    validation['request']['repeat'] = 5
    wire.write_text(''.join(json.dumps(event) + '\n' for event in events))
    with pytest.raises(ValueError, match='differs from the sealed journal'):
        study.replay(damaged, tmp_path / 'replay')
