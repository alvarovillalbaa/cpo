from benchmarks import recorded_bounded_certificate_backup as study
from cpo import Observation, Row


def test_audit_distinguishes_already_certified_and_unseen_opportunities():
    menu = {name: (gain, None) for name, gain in (('start', 0), ('deployed', 1), ('paid', 2),
                                                  ('partial', 3), ('unprobed', 4))}
    grades = {('start', str(case)): case < 2 for case in range(4)}
    grades.update({('paid', str(case)): True for case in range(3)})
    grades['partial', '0'] = True
    paid = {key: Observation(value, {}) for key, value in grades.items()}
    buckets, reads = study.attribute(menu, 'start', 'deployed', range(4), paid, range(4))
    assert buckets == {'unprobedTrials': 1, 'unprobedPasses': 3}
    assert reads == {'0': 1, '1': 1, '2': 2, '3': 3}


def test_backup_requires_enough_reads_for_validation_and_its_training_reserve():
    validation = (Row('1', 'validation', critical=True), Row('2', 'validation'))
    training = (Row('3', 'training'),)
    ledger = {('start', row.id): Observation(row.critical, {}) for row in validation}

    def read(prompt, row):
        assert (prompt, row.id) not in ledger
        ledger[prompt, row.id] = grade = Observation(True, {})
        return grade

    args = ('start', ('backup',), validation, training, read, ledger)
    assert study.backup_certificate(*args, cap=6, extra=1) is None
    assert study.backup_certificate(*args, cap=5, extra=2) is None
    assert len(ledger) == 2
    assert study.backup_certificate(*args, cap=6, extra=2) == ('backup', 2)
    assert len(ledger) == 4


def test_strict_training_veto_can_send_one_later_nominee_to_qualification():
    cells = {prompt: tuple((grade, None, False) for grade in outcomes) for prompt, outcomes in {
        'start': (0, 0, 0, 0, 1, 0, 0, 0, 0),
        'first': (0, 0, 0, 0, 1, 1, 1, 1, 0),
        'second': (1, 1, 0, 0, 1, 1, 1, 1, 1),
    }.items()}
    cohorts = ([0, 1, 2, 3], [4, 5], [6, 7], [8])
    args = (cells, 'start', ('first', 'second'), cohorts, 31, 12)
    point, trace, grades = study.run_trial(*args, 2)
    assert trace[2:4] == ('second', 'second') and grades == (1,)
    assert point['extraValidationLookups'] == 2 and point['qualificationLookups'] <= 4
    point, trace, grades = study.run_trial(*args, 1)
    assert trace[2:4] == ('start', 'start') and grades == (0,)
    assert point['extraValidationLookups'] == 0
