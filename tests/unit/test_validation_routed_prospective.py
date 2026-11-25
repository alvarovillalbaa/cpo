import json
from shutil import copytree

import pytest

from benchmarks import validation_routed_prospective as study
from cpo._contract import digest


@pytest.fixture
def archive(tmp_path):
    tasks, plan = study.prepare()
    source = tmp_path / 'first'
    result, audit = study.run_fixture(digest(plan), source)
    return tasks, plan, source, result, audit


def test_divergent_choices_get_distinct_holdouts_and_the_same_shared_drafts(archive, tmp_path):
    tasks, plan, source, result, audit = archive
    assert sum(plan['physicalLimitsByRole'].values()) == plan['requestCeiling'] == 2145
    assert result['physicalCallsByRole']['reflection'] == len(tasks) * 3 * 4
    assert result['decisions']['ticket'][study.CANDIDATE][0]['schedule'] == 'successive-halving/4/6'
    assert result['decisions']['outage'][study.CANDIDATE][0]['schedule'] == 'uniform/8/18'
    assert audit['differentPromptsFromAdaptive'] == ['outage']
    assert audit['candidateOnlyPhysicalSearch'] == {'evaluation': 6, 'admission': 6}
    assert audit['holdoutRequests'] == result['physicalCallsByRole']['qualification'] == 252
    assert audit['providerRequests'] == 0
    assert result['qualifiedOnBothMeasures']
    for verdict in result['verdicts'].values():
        assert set(verdict['comparisons']) == {'initial', *study.CONTROLS}
    assert study.replay(source, tmp_path / 'replay') == (result, audit)


def test_audit_rejects_merging_two_different_selected_prompts(archive):
    tasks, _, source, result, _ = archive
    selected = result['selected']['outage']
    selected[study.CANDIDATE] = selected[study.ADAPTIVE]
    with pytest.raises(ValueError, match='its own full holdout'):
        study.audit(result, source, tasks)


def test_replay_refuses_a_model_delivered_archive_before_creating_output(archive, tmp_path):
    _, _, source, _, _ = archive
    changed = tmp_path / 'model'
    copytree(source, changed)
    manifest = changed / 'plan.json'
    plan = json.loads(manifest.read_bytes())
    manifest.write_text(json.dumps({**plan, 'delivery': 'model'}))
    output = tmp_path / 'replay'
    with pytest.raises(ValueError, match='only replays fixture'):
        study.replay(changed, output)
    assert not output.exists()


def test_changed_candidate_request_breaks_exact_replay(archive, tmp_path):
    _, _, source, _, _ = archive
    changed = tmp_path / 'changed'
    copytree(source, changed)
    wire = changed / 'wire.jsonl'
    events = [json.loads(line) for line in wire.read_bytes().splitlines()]
    admission = next(event for event in events if event.get('arm') == study.CANDIDATE
                     and event['request']['role'] == 'admission')
    admission['request']['repeat'] = 1
    wire.write_text(''.join(json.dumps(event) + '\n' for event in events))
    with pytest.raises(ValueError, match='differs from the sealed journal'):
        study.replay(changed, tmp_path / 'replay')


def test_stale_seal_creates_no_directory(tmp_path):
    output = tmp_path / 'stale'
    with pytest.raises(ValueError, match='sealed plan'):
        study.run_fixture('stale', output)
    assert not output.exists()
