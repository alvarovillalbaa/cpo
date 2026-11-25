import json
from shutil import copytree

import pytest

from benchmarks import first_gain_independent_proposals as study
from cpo._contract import digest


@pytest.fixture
def experiment(tmp_path):
    tasks, plan = study.prepare()
    output = tmp_path / 'fixture'
    result, audit = study.run_fixture(digest(plan), output)
    return tasks, plan, output, result, audit


def wire(output):
    return [json.loads(line) for line in (output / 'wire.jsonl').read_bytes().splitlines()]


def test_independent_proposals_and_cycle_admission_replay(experiment, tmp_path):
    tasks, plan, output, result, audit = experiment
    assert study.replay(output, tmp_path / 'replay') == (result, audit)
    assert audit['providerRequests'] == 0
    assert set(audit['draftRequestsByArm']) == set(study.ARMS)
    assert all(0 < count <= len(tasks) * study.CYCLES * study.DRAFT_CAP
               for count in audit['draftRequestsByArm'].values())
    assert sum(audit['draftRequestsByArm'].values()) == result['physicalCallsByRole']['reflection']
    assert sum(result['physicalCallsByRole'].values()) <= plan['requestCeiling']
    for task, arms in result['decisions'].items():
        combined = [proposal for steps in arms.values() for step in steps for proposal in step['roster']]
        assert len(combined) == len(set(combined))
        for steps in arms.values():
            if task == 'outage':
                assert steps[0]['admission'] == 'rejected'
                assert steps[1]['start'] == study.grounded.BASELINE
            assert steps[-1]['start'] == steps[-2]['prompt']
    sequential = [event['request']['input'] for event in wire(output)
                  if event.get('arm') == study.parent.witness.GEPA[0]
                  and event['request']['role'] == 'reflection' and event['request']['task'] == 'warehouse']
    assert result['decisions']['warehouse'][study.parent.witness.GEPA[0]][0]['drafts'] == 2
    assert sequential[1]['current'] == result['decisions']['warehouse'][study.parent.witness.GEPA[0]][0]['roster'][0]
    assert sequential[1]['recentFeedback']


def test_training_audit_rejects_heldout_feedback(experiment):
    tasks, _, output, result, _ = experiment
    events = wire(output)
    draft = next(event['request'] for event in events if event.get('request', {}).get('role') == 'reflection')
    draft['input']['recentFeedback'][0]['id'] = tasks[draft['task']]['holdout'][0]['id']
    with (output / 'wire.jsonl').open('w') as handle:
        for event in events:
            handle.write(json.dumps(event) + '\n')
    with pytest.raises(ValueError, match='outside its current training panel'):
        study.audit(tasks, result, output)


def test_stale_seal_and_model_archive_do_not_create_output(experiment, tmp_path):
    _, _, source, _, _ = experiment
    output = tmp_path / 'refused'
    with pytest.raises(ValueError, match='sealed plan'):
        study.run_fixture('stale', output)
    assert not output.exists()
    model = tmp_path / 'model'
    copytree(source, model)
    manifest = model / 'plan.json'
    record = json.loads(manifest.read_bytes())
    manifest.write_text(json.dumps({**record, 'delivery': 'model'}))
    with pytest.raises(ValueError, match='Only fixture archives'):
        study.replay(model, output)
    assert not output.exists()
