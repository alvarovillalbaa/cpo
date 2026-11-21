import pytest

from benchmarks import recorded_certificate_allowance_transfer as study


def test_every_panel_is_enrolled_by_subject_identity_and_models_are_disjoint():
    plan, discovery, groups, _ = study.prepare()
    original_tasks = {(cohort, subject) for cohort, subject, _, _ in discovery}
    original_models = {model for _, _, model, _ in discovery}
    assert plan['effectiveExtraReads'] == 4
    assert tuple(plan['caseCounts']) == (10, 6, 4)
    assert len(groups[study.NEW_TASKS]) == 32
    assert len(groups[study.KNOWN_TASKS]) == 12
    for group, panels in groups.items():
        for cohort, subject, model, _ in panels:
            assert ((cohort, subject) in original_tasks) == (group == study.KNOWN_TASKS)
            assert model not in original_models


def test_same_model_on_new_task_is_not_disjoint_transfer():
    discovery = [('LMentry', 'old task', 'model', ())]
    targets = [('LMentry', 'new task', 'model', ()), ('LMentry', 'old task', 'other model', ())]
    with pytest.raises(ValueError, match='disjoint model checkpoints'):
        study.partition(discovery, targets)
