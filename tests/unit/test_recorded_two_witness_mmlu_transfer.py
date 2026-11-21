import pytest

from benchmarks import recorded_two_witness_mmlu_transfer as study


def test_mmlu_enrollment_keeps_every_panel_on_disjoint_tasks_and_checkpoints():
    plan, panels = study.prepare()
    assert len(panels) == 28
    assert len({subject for _, subject, _, _ in panels}) == 14
    assert len({model for _, _, model, _ in panels}) == 4
    assert len(plan['excludedPreviouslyExaminedTasks']) == 4
    assert {subject for _, subject, _ in plan['excludedPreviouslyExaminedTasks']} == {
        'formal_logic', 'world_religions',
    }
    assert plan['primary'] == 'both-witnesses-before-cut'
    assert tuple(plan['caseCounts']) == (10, 6, 4)


def test_new_mmlu_task_cannot_reuse_a_checkpoint():
    with pytest.raises(ValueError, match='disjoint model checkpoints'):
        study.enroll([('MMLU', 'new', 'model', [])], [('MMLU', 'earlier', 'model', [])])


def test_hindsight_proof_ceiling_requires_a_gain_on_the_paid_training_half():
    cells = {'start': [(0,)] * 6, 'higher-heldout': [(n,) for n in (0, 1, 1, 1, 1, 1)],
             'eligible': [(n,) for n in (1, 0, 1, 1, 1, 0)]}
    cohorts = ((0, 1), (2,), (3,), (4, 5))
    assert study.ceilings(cells, 'start', ('higher-heldout', 'eligible'), cohorts) == (0, 2, 1)
