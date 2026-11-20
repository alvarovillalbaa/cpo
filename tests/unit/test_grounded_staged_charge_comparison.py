"""Verify causal charge reuse without expanding the physical comparison."""

import json

import pytest

from benchmarks import grounded, grounded_staged_fixture
from benchmarks import grounded_staged_charge_comparison as trial
from benchmarks import grounded_staged_paired_rewrite_comparison as previous
from benchmarks.grounded_staged_policy_comparison import CACHED_OPENING_READS, CHARGED, Journal, PAIRED
from benchmarks.grounded_staged import CACHED_OPENING
from cpo._contract import digest


def test_charge_arm_gets_only_an_acquired_native_reply(tmp_path):
    dispatched = []

    def respond(request):
        dispatched.append(request)
        return trial.PricedReply('{}', 27)

    plan = {'arms': [CACHED_OPENING, PAIRED, CHARGED], 'searchCap': CACHED_OPENING_READS, 'repeats': 1,
            'logicalLimitsByRole': {'evaluation': 4}, 'physicalLimitsByRole': {'evaluation': 1}}
    request = {'task': 'ticket', 'role': 'evaluation', 'instruction': 'start', 'input': 'case'}
    with (tmp_path / 'wire.jsonl').open('x') as wire:
        journal = Journal(wire, plan, respond)
        with pytest.raises(grounded.ResponderFailed):
            journal.send(CHARGED, request)
        assert not dispatched
        assert journal.send('cpo', request) == '{}'
        with pytest.raises(grounded.ResponderFailed):
            journal.send(CHARGED, request)
        assert journal.send(CACHED_OPENING, request) == '{}'
        assert journal.send(PAIRED, request) == '{}'
        assert journal.send(CHARGED, request) == trial.PricedReply('{}', 27)
        assert dispatched == [request]
        assert journal.search_uses[CHARGED] == journal.search_uses[CACHED_OPENING] == [1]


def test_fixtures_replay_charges_and_share_confirmation(tmp_path):
    groups, plan, _ = trial.prepare()
    _, old_plan, _ = previous.prepare()
    assert plan['physicalLimitsByRole'] == old_plan['physicalLimitsByRole']
    assert plan['developmentRequestCeiling'] == old_plan['developmentRequestCeiling'] == 1920
    answers = {row['input']: row['expected'] for task in groups.values()
               for split in ('holdout', 'confirmation') for row in task[split]}

    def fixture(request):
        if request['role'] == 'qualification':
            return json.dumps(answers[request['input']])
        return grounded_staged_fixture.respond(request)

    def priced(request):
        text = fixture(request)
        if request['role'] == 'evaluation':
            return trial.PricedReply(text, len(request['input']) + len(request['instruction']))
        return text

    old, development = tmp_path / 'v5', tmp_path / 'v6'
    previous.run(digest(old_plan), old, fixture, delivery='fixture')
    result = trial.run(digest(plan), development, priced, delivery='fixture')
    with (development / 'wire.jsonl').open() as wire:
        normalized = [dict((key, value) for key, value in json.loads(row).items() if key != 'chargeMicrousd')
                      for row in wire]
    assert normalized == [json.loads(row) for row in (old / 'wire.jsonl').read_text().splitlines()]
    uses = result['developmentSearchSamplesByArm']
    assert set(uses[CHARGED]) <= set(uses[CACHED_OPENING])
    assert all(decisions[CHARGED] == decisions[PAIRED] == decisions[CACHED_OPENING]
               for decisions in result['admissionDecisions'].values())
    assert trial.replay(development, tmp_path / 'replayed') == result
    _, bound, _ = trial.prepare(development)
    assert bound['confirmationRequestCeiling'] == 288
    assert bound['physicalLimitsByRole'] == {'qualification': 288}
    panel = tmp_path / 'confirmation'
    confirmed = trial.run(digest(bound), panel, priced, delivery='fixture', development=development)
    assert all(row['passes'][CHARGED] == row['passes'][PAIRED] == row['passes'][CACHED_OPENING]
               for cases in confirmed['holdout'].values() for row in cases)
    assert trial.replay(panel, tmp_path / 'panel-replayed', development=development) == confirmed
