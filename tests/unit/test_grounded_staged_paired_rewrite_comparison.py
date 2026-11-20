"""Verify the paired arm uses only native replies and can bind a panel."""

import json

import pytest

from benchmarks import grounded, grounded_staged_fixture
from benchmarks import grounded_staged_opening_dominance_comparison as previous
from benchmarks import grounded_staged_paired_rewrite_comparison as trial
from benchmarks.grounded_staged import CACHED_OPENING, PAIRED_FIELD_REWRITE
from benchmarks.grounded_staged_policy_comparison import Journal
from cpo._contract import digest


def test_paired_rewrite_cannot_dispatch_or_reuse_an_unowned_sample(tmp_path):
    dispatched = []
    frozen = {'searchCap': 24, 'repeats': 1, 'logicalLimitsByRole': {'evaluation': 3},
              'physicalLimitsByRole': {'evaluation': 1}}
    request = {'task': 'ticket', 'role': 'evaluation', 'instruction': 'start', 'input': 'case'}
    wire = tmp_path / 'wire.jsonl'
    with wire.open('x') as output:
        journal = Journal(output, frozen, lambda request: dispatched.append(request) or '{}')
        with pytest.raises(grounded.ResponderFailed) as rejected:
            journal.send(PAIRED_FIELD_REWRITE, request)
        assert 'native GEPA' in str(rejected.value.__cause__)
        journal.send('cpo', request)
        with pytest.raises(grounded.ResponderFailed) as rejected:
            journal.send(PAIRED_FIELD_REWRITE, request)
        assert 'native GEPA' in str(rejected.value.__cause__)
        journal.send(CACHED_OPENING, request)
        assert journal.send(PAIRED_FIELD_REWRITE, request) == '{}'
        assert dispatched == [request]
        assert journal.search_uses[PAIRED_FIELD_REWRITE] == journal.search_uses[CACHED_OPENING] == [1]
    assert len(wire.read_bytes().splitlines()) == 2


def test_shared_replies_keep_the_wire_and_allow_independent_confirmation(tmp_path):
    groups, plan, _ = trial.prepare()
    _, prior, _ = previous.prepare()
    assert plan['physicalLimitsByRole'] == prior['logicalLimitsByRole']
    assert plan['developmentRequestCeiling'] == 1920
    answers = {row['input']: row['expected'] for task in groups.values()
               for split in ('holdout', 'confirmation') for row in task[split]}

    def respond(request):
        if request['role'] == 'qualification':
            return json.dumps(answers[request['input']])
        return grounded_staged_fixture.respond(request)

    old, development = tmp_path / 'v4', tmp_path / 'v5'
    previous.run(digest(prior), old, respond, delivery='fixture')
    result = trial.run(digest(plan), development, respond, delivery='fixture')
    assert (development / 'wire.jsonl').read_bytes() == (old / 'wire.jsonl').read_bytes()
    uses = result['developmentSearchSamplesByArm']
    assert set(uses[PAIRED_FIELD_REWRITE]) < set(uses[CACHED_OPENING])
    assert PAIRED_FIELD_REWRITE in result['outcome']['qualifyingPolicies']
    assert trial.replay(development, tmp_path / 'replay') == result
    with pytest.raises(ValueError, match='current comparison seal'):
        trial.prepare(old)
    _, bound, _ = trial.prepare(development)
    assert bound['physicalLimitsByRole'] == {'qualification': 288}
    confirmation = tmp_path / 'panel'
    panel = trial.run(digest(bound), confirmation, respond, delivery='fixture', development=development)
    assert PAIRED_FIELD_REWRITE in panel['qualifyingInBothStages']
    assert trial.replay(confirmation, tmp_path / 'panel-replay', development=development) == panel
