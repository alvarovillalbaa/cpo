import pytest

from benchmarks import recorded_shortlist_model_transfer as study


def test_confirmation_holds_out_both_models_and_partitions_every_panel_by_task_identity():
    plan, groups, tuning, _ = study.prepare()
    tuning_models = {panel[2] for panels in tuning.values() for panel in panels}
    assert plan['primary'] == 'both-witnesses-before-cut'
    assert len(groups[study.KNOWN_TASKS]) == 28
    assert len(groups[study.NEW_TASKS]) == 4
    assert {(cohort, subject) for cohort, subject, _, _ in groups[study.NEW_TASKS]} == {
        ('BBH', 'bbh-causal_judgement'), ('LMentry', 'lmentry-ends_with_word'),
    }
    assert {model for panels in groups.values() for _, _, model, _ in panels} == {'flan-t5-xl', 'minotaur-15b'}
    assert all(panel[2] not in tuning_models for panels in groups.values() for panel in panels)


def test_new_task_on_tuning_model_is_rejected():
    with pytest.raises(ValueError, match='different model checkpoints'):
        study.partition([('BBH', 'known', 'same-model')], [('BBH', 'new', 'same-model', [])])
