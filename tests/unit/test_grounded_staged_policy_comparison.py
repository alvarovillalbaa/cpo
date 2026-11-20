import json

import pytest

from benchmarks import grounded, grounded_staged_fixture
from benchmarks import grounded_staged_policy_comparison as trial
from benchmarks.grounded_staged_combined_fixture import mixed_fixture
from cpo._contract import digest


def test_opening_control_shares_samples_and_produces_bound_confirmation(tmp_path, monkeypatch):
    groups, plan, _ = trial.prepare()
    assert plan['developmentRequestCeiling'] == 1920
    assert plan['cachedGepaOpening']['minibatch'] == 2
    assert plan['cachedGepaOpening']['laterProposals'] == 0
    observed = set()
    opening_tasks = []
    native_widths = []
    native = trial.gepa_disjoint_cases.select

    def track_native(*args, **kwargs):
        native_widths.append(kwargs['width'])
        return native(*args, **kwargs)

    monkeypatch.setattr(trial.gepa_disjoint_cases, 'select', track_native)

    def respond(request):
        if request['instruction'] == grounded.OPENING:
            opening_tasks.append(request['task'])
        if request['role'] != 'reflection':
            key = json.dumps(request, sort_keys=True)
            assert key not in observed
            observed.add(key)
        return mixed_fixture(request)

    archive = tmp_path / 'dev'
    result = trial.run(digest(plan), archive, respond, delivery='fixture')
    assert sorted(opening_tasks) == ['outage', 'ticket', 'warehouse']
    assert sorted(native_widths) == [1, 1, 1, 2, 2, 2]
    assert result['outcome']['qualifyingPolicies'] == ['cpo']
    assert result['outcome']['stagedVersusOpeningOnly']['addedPassesByTask'] == {'ticket': 0, 'warehouse': 16, 'outage': 8}
    assert result['searchCallsByArm']['opening-only'] == 119
    assert result['searchCallsByArm']['cpo'] == 143
    assert len(result['developmentSearchSamplesByArm']['shared']) == 3
    assert 'gepa-cached-opening' in result['outcome']['byPolicy']['cpo']['comparisons']
    journal = [json.loads(line)['request'] for line in (archive / 'wire.jsonl').read_text().splitlines()[::2]]
    for index in result['developmentSearchSamplesByArm']['gepa-cached-opening']:
        sample = journal[index - 1]
        split = {'evaluation': 'validation', 'admission': 'admission'}[sample['role']]
        assert sample['input'] in {row['input'] for row in groups[sample['task']][split]}
    assert trial.replay(archive, tmp_path / 'dev-replay') == result

    _, panel, _ = trial.prepare(archive)
    assert panel['confirmationRequestCeiling'] == 288
    assert panel['developmentQualifyingPolicies'] == ['cpo']
    assert panel['promptsSha256'] == digest(result['selected'])
    confirmation = tmp_path / 'panel'
    outcome = trial.run(digest(panel), confirmation, mixed_fixture, delivery='fixture', development=archive)
    assert outcome['qualifyingInBothStages'] == ['cpo']
    assert outcome['selected'] == result['selected']
    assert trial.replay(confirmation, tmp_path / 'panel-replay', development=archive) == outcome

    with pytest.raises(ValueError, match='delivery must match'):
        trial.run(digest(panel), tmp_path / 'model', lambda *_: pytest.fail('Responder called'),
                  delivery='model', development=archive)
    assert not (tmp_path / 'model').exists()


def test_opening_only_can_qualify_without_staged_policy(tmp_path, monkeypatch):
    choose = trial.staged.choose
    failing = 'test instruction with no valid holdout replies'
    groups, plan, _ = trial.prepare()
    answers = {row['input']: row['expected'] for splits in groups.values()
               for part in ('holdout', 'confirmation') for row in splits[part]}

    def force_controlled_holdout(task, groups, dispatch, **flags):
        selected, decisions = choose(task, groups, dispatch, **flags)
        return {**dict.fromkeys(selected, grounded.BASELINE), 'cpo': failing}, decisions

    def respond(request):
        if request['role'] == 'qualification':
            return ('{}' if request['instruction'] in (failing, grounded.BASELINE)
                    else json.dumps(answers[request['input']]))
        return grounded_staged_fixture.respond(request)

    monkeypatch.setattr(trial.staged, 'choose', force_controlled_holdout)
    archive = tmp_path / 'only-opening-passes'
    result = trial.run(digest(plan), archive, respond, delivery='fixture')
    assert result['outcome']['qualifyingPolicies'] == ['opening-only']
    _, panel, _ = trial.prepare(archive)
    assert panel['developmentQualifyingPolicies'] == ['opening-only']
    control = trial.run(digest(panel), tmp_path / 'panel', respond, delivery='fixture', development=archive)
    assert control['qualifyingInBothStages'] == ['opening-only']


def test_stale_seal_and_tampered_development_fail_closed(tmp_path):
    _, plan, _ = trial.prepare()
    archive = tmp_path / 'dev'
    old_policy_seal = '1c3c2cd7668bdc0cbe8e2e68cbe24ec85f12b451ace63571219857fdf6b5bf2e'
    with pytest.raises(ValueError, match='current comparison seal'):
        trial.run(old_policy_seal, archive, lambda *_: pytest.fail('Responder called'), delivery='fixture')
    assert not archive.exists()
    trial.run(digest(plan), archive, mixed_fixture, delivery='fixture')
    output = archive / 'result.json'
    output.write_bytes(output.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='differs from its replay'):
        trial.prepare(archive)
