import json

import pytest

from benchmarks import settled_episode_prospective as study
from benchmarks.settled_episode_prospective_fixture import responder
from cpo._contract import digest


def test_roles_are_disjoint_and_later_panels_keep_critical_cases():
    tasks, plan = study.prepare()
    for groups in tasks.values():
        rows = [row for panel in groups.values() for row in panel]
        assert len({row['id'] for row in rows}) == len({row['input'] for row in rows}) == len(rows)
        assert len(groups['validation']) == study.CYCLES * study.VALIDATION
        assert all(not row['critical'] for row in groups['validation'])
        assert all(any(row['critical'] for row in groups[split]) for split in ('admission', 'holdout', 'confirmation'))
    assert digest(tasks) == plan['datasetSha256']
    assert plan['requestCeiling'] == sum(plan['physicalLimitsByRole'].values())


def test_all_four_real_runners_execute_and_replay_the_same_archive(tmp_path):
    tasks, plan = study.prepare()
    original = tmp_path / 'fixture'
    result = study.run(digest(plan), original, responder(tasks), delivery='fixture')
    assert study.replay(original, tmp_path / 'replay') == result
    assert all(sizes == [8, 8, 8] for sizes in result['rosterSizes'].values())
    for arms in result['decisions'].values():
        for arm in ('gepa-sequential', 'gepa-batched'):
            assert any(cycle['challengerLookups'] for cycle in arms[arm])
    second = {task: arms[study.FEEDBACK][1] for task, arms in result['decisions'].items()}
    assert {task: step['schedule'] for task, step in second.items()} == {
        'ticket': 'successive-halving/8/14', 'warehouse': 'fitted-opening-repair', 'outage': 'retain-start',
    }
    assert second['outage']['admissionLookups'] == second['outage']['validationLookups'] == 0
    assert result['physicalCallsByRole']['reflection'] == plan['physicalLimitsByRole']['reflection']
    assert sum(result['physicalCallsByRole'].values()) < sum(result['logicalCallsByRole'].values())


def test_duplicate_pair_is_dropped_for_all_arms(tmp_path):
    tasks, plan = study.prepare()
    normal = responder(tasks)
    drafts = {}

    def repeated(request):
        if request['role'] == 'reflection':
            return drafts.setdefault(request['task'], normal(request))
        return normal(request)

    result = study.run(digest(plan), tmp_path / 'duplicate', repeated, delivery='fixture')
    assert all(sizes == [2, 0, 0] for sizes in result['rosterSizes'].values())
    assert all(steps[-1]['nominee'] is None for arms in result['decisions'].values() for steps in arms.values())


def test_wrong_seal_and_incomplete_wire_leave_a_distinct_failure(tmp_path):
    _, plan = study.prepare()
    fresh = tmp_path / 'stale'

    def unavailable(_request):
        raise OSError('Fixture simulates a lost reply')

    with pytest.raises(ValueError, match='sealed plan'):
        study.run('wrong', fresh, unavailable, delivery='fixture')
    assert not fresh.exists()
    partial = tmp_path / 'partial'
    with pytest.raises(OSError, match='lost reply'):
        study.run(digest(plan), partial, unavailable, delivery='fixture')
    intent, = (partial / 'wire.jsonl').read_text().splitlines()
    assert json.loads(intent)['request']['role'] == 'reflection'
    assert not (partial / 'result.json').exists()
