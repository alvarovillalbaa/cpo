"""Keep prospective episode gates, case splits, and replay reproducible."""

import json

import pytest

from benchmarks import grounded, grounded_staged, grounded_witness_episode as study, typed_policy
from benchmarks.grounded_witness_episode_fixture import responder


def test_cohorts_hold_out_facts_and_identities():
    tasks = study.cohorts()
    assert set(tasks) == set(typed_policy.TASKS)
    archived = (typed_policy.cohorts(grounded.SEED), grounded_staged.cohorts())
    ids = set()
    for task, splits in tasks.items():
        assert {key: len(rows) for key, rows in splits.items()} == study.SPLITS
        excluded = {row['input'] for groups in archived for rows in groups[task].values() for row in rows}
        for rows in splits.values():
            for row in rows:
                assert row['id'] not in ids
                assert row['input'] not in excluded
                ids.add(row['id'])
                excluded.add(row['input'])


def test_qualifying_episode_confirms_and_rejects_partial_replay(tmp_path):
    pytest.importorskip('gepa')
    tasks, plan, _ = study.prepare()
    assert plan['requestCeiling'] == 2712
    development = tmp_path / 'development'
    reply = responder(tasks, 'qualifying')
    result = study.run(study.digest(plan), development, reply, delivery='fixture')
    assert result['qualifiedOnBothMeasures']
    assert result['physicalCallsByRole']['reflection'] == len(tasks) * study.CYCLES
    for prompts in result['selected'].values():
        assert prompts[study.CANDIDATE] == prompts['cpo-four-admissions']
        assert prompts[study.GEPA[0]] == prompts[study.GEPA[1]] != prompts[study.CANDIDATE]
    assert study.replay(development, tmp_path / 'development-replay') == result

    _, bound, _ = study.prepare(development)
    assert bound['physicalLimitsByRole'] == {'qualification': 144}
    with pytest.raises(ValueError, match='matching delivery'):
        study.run(study.digest(bound), tmp_path / 'wrong-delivery', reply, delivery='model', development=development)
    confirmation = tmp_path / 'confirmation'
    confirmed = study.run(study.digest(bound), confirmation, reply, delivery='fixture', development=development)
    assert confirmed['qualifiedOnBothMeasures']
    assert confirmed['selected'] == result['selected']
    assert confirmed['logicalCallsByRole'] == confirmed['physicalCallsByRole'] == bound['physicalLimitsByRole']
    assert study.replay(confirmation, tmp_path / 'confirmation-replay', development=development) == confirmed

    wire = confirmation / 'wire.jsonl'
    wire.write_bytes(b''.join(wire.read_bytes().splitlines(keepends=True)[:-1]))
    with pytest.raises(ValueError, match='incomplete reply'):
        study.replay(confirmation, tmp_path / 'broken-replay', development=development)


def test_rejected_admission_spends_the_attempt_and_prevents_confirmation(tmp_path):
    pytest.importorskip('gepa')
    tasks, plan, _ = study.prepare()
    development = tmp_path / 'development'
    result = study.run(study.digest(plan), development, responder(tasks, 'rejected'), delivery='fixture')
    assert not result['qualifiedOnBothMeasures']
    for choices in result['admissions'].values():
        for arm in (study.CANDIDATE, *study.GEPA):
            assert [decision['admission'] for decision in choices[arm]] == ['rejected']
        assert [decision['admission'] for decision in choices['cpo-four-admissions']] == ['rejected'] * study.CYCLES
    wire = [json.loads(line) for line in (development / 'wire.jsonl').read_text().splitlines()]
    assert any(entry.get('request', {}).get('role') == 'admission' for entry in wire)
    with pytest.raises(ValueError, match='qualifying development archive'):
        study.prepare(development)
