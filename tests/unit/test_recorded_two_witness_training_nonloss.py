from benchmarks import recorded_two_witness_training_nonloss as study
from cpo import Observation, Row


def test_training_nonloss_accepts_a_tie_and_still_rejects_a_loss():
    rows = (Row('a', 'training'), Row('b', 'training'))

    def tied(prompt, row):
        return Observation((prompt == 'old') == (row.id == 'a'), {})

    assert not study.corroborate('old', 'new', rows, tied, minimum_gain=1, remaining=4, seed=3)
    assert study.training_nonloss('old', 'new', rows, tied, minimum_gain=1, remaining=4, seed=3)
    assert not study.training_nonloss(
        'old', 'new', rows, lambda prompt, _: Observation(prompt == 'old', {}),
        minimum_gain=1, remaining=4, seed=3,
    )


def test_confirmation_keeps_only_previously_unexamined_tasks():
    plan, cohorts, _ = study.prepare()
    assert len(cohorts['previous-mmlu']) == 28
    assert len(cohorts['disjoint-mmlu']) == 10
    assert {subject for _, subject, _ in plan['excludedPreviouslyExaminedTasks']} == {'world_religions'}
    assert plan['minimumTrainingGain'] == {study.STRICT: 1, study.NONLOSS: 0}
