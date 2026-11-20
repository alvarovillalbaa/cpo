import json

import pytest

from benchmarks import grounded, grounded_staged_fixture
from benchmarks import grounded_staged_policy_comparison as trial
from benchmarks.grounded_staged_combined_fixture import mixed_fixture
from cpo._contract import digest


def test_opening_control_shares_samples_and_produces_bound_confirmation(tmp_path):
    _, plan, _ = trial.prepare()
    assert plan['developmentRequestCeiling'] == 1644
    observed = set()
    opening_tasks = []

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
    assert result['outcome']['qualifyingPolicies'] == ['cpo']
    assert result['outcome']['stagedVersusOpeningOnly']['addedPassesByTask'] == {'ticket': 0, 'warehouse': 16, 'outage': 8}
    assert result['searchCallsByArm']['opening-only'] == 119
    assert result['searchCallsByArm']['cpo'] == 143
    assert len(result['developmentSearchSamplesByArm']['shared']) == 3
    assert trial.replay(archive, tmp_path / 'dev-replay') == result

    _, panel, _ = trial.prepare(archive)
    assert panel['confirmationRequestCeiling'] == 240
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
    with pytest.raises(ValueError, match='current comparison seal'):
        trial.run(plan['combinedPlanSha256'], archive, lambda *_: pytest.fail('Responder called'), delivery='fixture')
    assert not archive.exists()
    trial.run(digest(plan), archive, mixed_fixture, delivery='fixture')
    output = archive / 'result.json'
    output.write_bytes(output.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='differs from its replay'):
        trial.prepare(archive)
