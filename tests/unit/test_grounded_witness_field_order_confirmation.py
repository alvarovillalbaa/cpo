import json

import pytest

from benchmarks import grounded_witness_field_order_confirmation as trial


@pytest.fixture(scope='module')
def development(tmp_path_factory):
    root = tmp_path_factory.mktemp('field-order') / 'development'
    groups, plan, _ = trial.ordered.prepare()
    trial.ordered.run(trial.digest(plan), root, trial.ordered.fixture_responder(groups, 'qualifying'),
                      delivery='fixture')
    return root


@pytest.mark.parametrize('profile', trial.PROFILES)
def test_archive_replays_and_keeps_the_bound_development_unchanged(tmp_path, development, profile):
    groups, plan, prior, samples = trial.prepare(development)
    parent = trial.ordered.prepare(development)[1]
    assert plan['parentConfirmationPlanSha256'] == trial.digest(parent)
    assert plan['requestCeiling'] == parent['requestCeiling'] == len(samples) == 128
    assert plan['developmentArchiveSha256'] == parent['developmentArchiveSha256']
    assert plan['gate'] == parent['gate']
    assert prior['qualifiedOnBothMeasures']
    before = trial.archive_bytes(development)

    archive = tmp_path / 'confirmation'
    result = trial.run(trial.digest(plan), archive, trial.fixture(groups, plan, profile),
                       development=development, delivery='fixture')
    assert trial.replay(archive, tmp_path / 'replayed', development=development) == result
    assert trial.archive_bytes(development) == before
    scored = result['scoring']['scoredRequests']
    assert set(result['physicalCallsByRole']) == {'qualification'}
    assert result['physicalCallsByRole']['qualification'] == scored
    if profile == 'shared-failure':
        assert not result['qualified']
        assert result['pairedGate'] == 'unmeasured'
        assert result['absoluteVerdict']['status'] == 'rejected'
        assert scored < len(samples)
        assert result['scoring']['firstUnsentSampleSha256'] == trial.digest(samples[scored].request)
    else:
        assert result['qualified'] and result['scoring']['completePanel']
        assert scored == len(samples)
        counts = result['absoluteVerdict']['passesByCase']
        assert all(passes == (1 if profile == 'single-miss' else 2)
                   for cases in counts.values() for passes in cases.values())


def test_stops_after_the_minimum_failing_prefix_for_each_reordered_case(development):
    groups, plan, prior, samples = trial.prepare(development)
    for task, ids in plan['absoluteGate']['caseIdsByTask'].items():
        for case in ids:
            respond = trial.fixture(groups, plan, 'shared-failure', case)
            reads = []

            def evaluate(sample):
                reads.append(sample)
                return trial.grounded.score(respond(sample.request), sample.case['expected'])[0]

            result = trial.score(samples, plan, prior['searchCosts'], evaluate)
            candidate = [index for index, sample in enumerate(samples, 1) if sample.case['id'] == case
                         and trial.evidence.CANDIDATE in sample.arms]
            assert len(candidate) == 2
            assert reads == samples[:candidate[-1]]
            assert result['absoluteVerdict']['failedCases'] == {task: [case]}
            assert not result['qualified']


def test_stale_seal_delivery_mismatch_and_tampered_archive_fail(tmp_path, development):
    groups, plan, _, _ = trial.prepare(development)
    failed = tmp_path / 'refused'
    for seal, delivery, message in (('invalid', 'fixture', 'current confirmation seal'),
                                    (trial.digest(plan), 'model', 'match development')):
        with pytest.raises(ValueError, match=message):
            trial.run(seal, failed, lambda _: pytest.fail('unexpected dispatch'),
                      development=development, delivery=delivery)
        assert not failed.exists()

    archive = tmp_path / 'archive'
    result = trial.run(trial.digest(plan), archive, trial.fixture(groups, plan, 'shared-failure'),
                       development=development, delivery='fixture')
    (archive / 'result.json').write_text(json.dumps({**result, 'qualified': True}), encoding='utf-8')
    with pytest.raises(ValueError, match='differs from exact replay'):
        trial.replay(archive, tmp_path / 'tampered', development=development)
