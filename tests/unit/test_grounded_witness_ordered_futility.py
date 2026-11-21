from collections import Counter
import json

import pytest

from benchmarks import grounded_witness_ordered_futility as ordered


def journal(path):
    entries = [json.loads(line) for line in (path / 'wire.jsonl').read_text().splitlines()]
    return list(zip(entries[::2], entries[1::2], strict=True))


def split_journal(path):
    entries = journal(path)
    search = [(intent, reply) for intent, reply in entries if intent['request']['role'] != 'qualification']
    scoring = [(ordered.digest(intent['request']), reply['response']) for intent, reply in entries
               if intent['request']['role'] == 'qualification']
    return search, scoring


@pytest.mark.parametrize('profile', ordered.PROFILES)
def test_development_preserves_search_and_exact_gate_under_the_new_order(tmp_path, profile):
    pytest.importorskip('gepa')
    groups, plan, _ = ordered.prepare()
    fixture = ordered.fixture_responder(groups, profile)
    before, after = tmp_path / 'original', tmp_path / 'ordered'
    baseline = ordered.original.run(ordered.study.PARENT_SEAL, before, fixture, delivery='fixture')
    outcome = ordered.run(ordered.digest(plan), after, fixture, delivery='fixture')

    for key in ('selected', 'admissions', 'additionalValidationUses', 'searchCosts', 'qualifiedOnBothMeasures'):
        assert outcome[key] == baseline[key]
    old_search, old_scoring = split_journal(before)
    new_search, new_scoring = split_journal(after)
    assert new_search == old_search
    samples = ordered.study.order(ordered.original.scoring_schedule(groups, outcome['selected'], 'holdout'),
                                  ordered.study.GATE)
    assert [key for key, _ in new_scoring] == [ordered.digest(sample.request) for sample in samples[:len(new_scoring)]]
    if profile == 'qualifying':
        assert outcome['verdicts'] == baseline['verdicts']
        assert Counter(new_scoring) == Counter(old_scoring)
        assert new_scoring != old_scoring
    else:
        assert 'holdout' not in outcome
        if profile == 'outage-scoring-failure':
            assert len(new_scoring) < len(old_scoring)
        else:
            assert not new_scoring
        assert outcome['scoring']['firstUnsentSampleSha256'] == ordered.digest(samples[len(new_scoring)].request)
        with pytest.raises(ValueError, match='complete, qualifying ordered development'):
            ordered.prepare(after)

    replay = tmp_path / 'exact-replay'
    assert ordered.replay(after, replay) == outcome
    assert ordered.archive_bytes(replay) == ordered.archive_bytes(after)


def test_new_plan_preserves_the_inherited_search_and_gate_contract():
    _, parent, _ = ordered.original.prepare()
    _, current, _ = ordered.prepare()
    changed = {'protocol', 'parentPlanSha256', 'sourceSha256'}
    assert {key for key in parent if current[key] != parent[key]} == changed
    assert {key: current['sourceSha256'][key] for key in parent['sourceSha256']} == parent['sourceSha256']
    assert current['parentPlanSha256'] == ordered.digest(parent)


def test_confirmation_binds_a_disjoint_scoring_only_archive_and_rejects_tampering(tmp_path):
    pytest.importorskip('gepa')
    groups, plan, _ = ordered.prepare()
    development = tmp_path / 'development'
    ordered.run(ordered.digest(plan), development, ordered.fixture_responder(groups, 'qualifying'), delivery='fixture')
    _, bound, prior = ordered.prepare(development)
    panel = tmp_path / 'confirmation'
    result = ordered.run(ordered.digest(bound), panel, ordered.fixture_responder(groups, 'qualifying'),
                         delivery='fixture', development=development)

    assert result['scoring']['scoringScheduleSha256'] == bound['scoringScheduleSha256']
    assert result['physicalCallsByRole'] == {'qualification': bound['requestCeiling']}
    assert result['qualifiedOnBothMeasures']
    assert result['selected'] == prior['selected']
    assert ordered.replay(panel, tmp_path / 'confirmation-replay', development=development) == result
    with pytest.raises(ValueError, match='delivery must match'):
        ordered.run(ordered.digest(bound), tmp_path / 'invalid', lambda _: pytest.fail('unexpected dispatch'),
                    delivery='model', development=development)
    assert not (tmp_path / 'invalid').exists()

    (panel / 'result.json').write_text(json.dumps({**result, 'qualifiedOnBothMeasures': False}), encoding='utf-8')
    with pytest.raises(ValueError, match='differs from exact replay'):
        ordered.replay(panel, tmp_path / 'tampered-replay', development=development)
