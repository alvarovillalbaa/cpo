"""T2 checks for exact futility proofs and complete-reply journal prefixes."""

from itertools import product
import json

import pytest

from benchmarks import grounded_witness_halving as parent, grounded_witness_halving_futility as study


def test_early_rejection_agrees_with_every_completion_of_small_shared_panels():
    arms = ('initial', *parent.ARMS)
    samples = []
    for case, repeat in product(('critical', 'ordinary'), range(2)):
        same = (parent.CANDIDATE, parent.original.CANDIDATE) if repeat else (parent.CANDIDATE,)
        for members in (same, tuple(arm for arm in arms if arm not in same)):
            samples.append(study.Sample({'task': 'only', 'repeat': repeat, 'arms': members},
                                        {'id': case, 'critical': case == 'critical'}, members))
    plan = {'gate': {'minimumTaskPasses': 2, 'minimumAddedPasses': 1, 'efficiencyPercent': 90}}
    prices = {arm: 12 for arm in parent.ARMS}
    prices[parent.CANDIDATE] = 10
    costs = {'logicalSearchUses': prices, 'attributedSearchRequests': {**prices, parent.original.CANDIDATE: 10}}

    completions = {}
    for bits in product((False, True), repeat=len(samples)):
        cells = {}
        for sample, passed in zip(samples, bits, strict=True):
            case, repeat = sample.case['id'], sample.request['repeat']
            row = cells.setdefault((case, repeat), {'id': case, 'repeat': repeat,
                                                   'critical': sample.case['critical'], 'passes': {}})
            row['passes'].update(dict.fromkeys(sample.arms, passed))
        verdicts = parent.finish(plan, {'only': list(cells.values())}, costs)
        completions[bits] = all(row['qualified'] for row in verdicts.values())
    assert any(completions.values()) and not all(completions.values())

    for bits, expected in completions.items():
        paid = iter(bits)
        status, output = study.score_until_rejected(samples, plan, costs, lambda _: next(paid))
        assert (status['status'] == 'qualified') == expected
        if status['completePanel']:
            assert 'holdout' in output
        else:
            prefix = bits[:status['scoredRequests']]
            assert all(not passes for path, passes in completions.items() if path[:len(prefix)] == prefix)
            assert 'holdout' not in output


@pytest.mark.parametrize(('profile', 'scored', 'scheduled'), (
    ('qualifying', 288, 288), ('rejected-admission', 0, 108), ('faulted-scoring', 20, 288)))
def test_scoring_wire_is_the_exact_paid_prefix_of_the_parent(tmp_path, profile, scored, scheduled):
    pytest.importorskip('gepa')
    groups, plan, _ = study.prepare()
    fixture = study.fixture_responder(groups, profile)
    plain, guarded = tmp_path / 'plain', tmp_path / 'guarded'
    expected = parent.run(study.PARENT_SEAL, plain, fixture, delivery='fixture')
    actual = study.run(study.digest(plan), guarded, fixture, delivery='fixture')
    assert actual['selected'] == expected['selected'] and actual['searchCosts'] == expected['searchCosts']
    assert actual['qualifiedOnBothMeasures'] == expected['qualifiedOnBothMeasures']
    assert actual['scoring']['scoredRequests'] == scored and actual['scoring']['scheduledRequests'] == scheduled
    wire = (guarded / 'wire.jsonl').read_bytes()
    assert (plain / 'wire.jsonl').read_bytes().startswith(wire)
    assert study.replay(guarded, tmp_path / 'replay') == actual
    if profile == 'qualifying':
        assert actual['holdout'] == expected['holdout'] and actual['verdicts'] == expected['verdicts']
    else:
        assert 'holdout' not in actual and 'firstUnsentSampleSha256' in actual['scoring']
        with pytest.raises(ValueError, match='exact, complete, qualifying'):
            study.prepare(guarded)


def test_confirmation_stops_on_a_fault_and_a_tampered_terminal_receipt_cannot_replay(tmp_path):
    pytest.importorskip('gepa')
    groups, plan, _ = study.prepare()
    development, panel = tmp_path / 'development', tmp_path / 'confirmation'
    study.run(study.digest(plan), development, study.fixture_responder(groups, 'qualifying'), delivery='fixture')
    _, bound, _ = study.prepare(development)
    result = study.run(study.digest(bound), panel, study.fixture_responder(groups, 'faulted-scoring'),
                       delivery='fixture', development=development)
    assert result['physicalCallsByRole'] == {'qualification': 10}
    assert result['scoring']['scheduledRequests'] == bound['requestCeiling'] == 128
    assert study.replay(panel, tmp_path / 'confirmation-replay', development=development) == result
    result['scoring']['firstUnsentSampleSha256'] = '0' * 64
    (panel / 'result.json').write_text(json.dumps(result), encoding='utf-8')
    with pytest.raises(ValueError, match='differs from its exact replay'):
        study.replay(panel, tmp_path / 'tampered-replay', development=development)
