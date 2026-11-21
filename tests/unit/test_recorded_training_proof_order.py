from benchmarks import recorded_training_proof_order as trial
from cpo import Observation, Row


def test_qualification_can_go_first_when_paid_validation_excludes_a_backup():
    validation = tuple(Row(case, 'validation') for case in ('v1', 'v2', 'v3'))
    training = tuple(Row(case, 'training') for case in ('t1', 't2'))
    ledger = {('start', row.id): Observation(row.id == 'v1', {}) for row in validation}
    ledger['alternate', 'v1'] = Observation(True, {})
    assert trial.can_defer('start', 'first', ('first', 'alternate'), validation, training, ledger, 20)

    ledger['alternate', 'v2'] = Observation(True, {})
    assert not trial.can_defer('start', 'first', ('first', 'alternate'), validation, training, ledger, 20)


def test_defer_needs_a_nominee_and_the_full_training_reserve():
    validation, training = (Row('v', 'validation'),), (Row('t', 'training'),)
    ledger = {('start', 'v'): Observation(False, {})}
    assert not trial.can_defer('start', 'start', ('first',), validation, training, ledger, 20)
    assert not trial.can_defer('start', 'first', ('first',), validation, training, ledger, 2)
    assert trial.can_defer('start', 'first', ('first',), validation, training, ledger, 3)


def test_aime_replay_preserves_deployment_through_the_deferred_branch():
    plan, archive, _ = trial.prepare()
    settings = plan['datasets']['aime']
    cells = trial.math.load_cells('aime', archive['aime']['record'])
    deferred = skipped = vetoed = 0
    for seed in settings['seeds'][:4]:
        cohorts = trial.math.split_cases(len(next(iter(cells.values()))), seed, settings['cohorts'])
        for start in tuple(cells)[1:]:
            roster = tuple(prompt for prompt in cells if prompt != start)
            original = trial.backup.run_trial(cells, start, roster, cohorts, seed, trial.backup.PRECHECK, 180)
            point, trace, grades = trial.run_trial(cells, start, roster, cohorts, seed, 180)
            assert trace[3] == original[1][3] and grades == original[2]
            deferred += point.get('deferredTraining', 0)
            skipped += point.get('trainingSkippedAfterQualification', 0)
            vetoed += point.get('trainingVetoAfterQualification', 0)
    assert deferred > 0 and skipped > 0 and vetoed > 0
