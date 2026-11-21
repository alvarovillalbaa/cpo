from collections import Counter
from itertools import product

from benchmarks import recorded_incumbent_training_precheck as study
from cpo import Observation, Row


def test_precheck_stops_only_with_a_complete_perfect_panel():
    validation = (Row('v1', 'validation'), Row('v2', 'validation'))
    training = (Row('t1', 'training'), Row('t2', 'training'))
    for outcomes in product((False, True), repeat=4):
        grades = dict(zip(validation + training, outcomes, strict=True))
        for mode in study.MODES:
            ledger, audit = {}, Counter()

            def read(prompt, row):
                key = (prompt, row.id)
                assert prompt == 'incumbent' and key not in ledger
                ledger[key] = grade = Observation(grades[row], {})
                return grade

            worst_case = 2 * len(validation) + 3 * len(training)
            args = ('incumbent', ('challenger',), validation, training, read, ledger)
            assert not study.precheck(*args, mode=mode, cap=worst_case - 1, audit=audit)
            assert not ledger and not audit
            perfect_validation = mode == study.VALIDATION_FIRST and all(outcomes[:2])
            assert study.precheck(*args, mode=mode, cap=worst_case, audit=audit) == (
                perfect_validation or all(outcomes[2:]))
            expected = []
            if mode == study.VALIDATION_FIRST:
                expected.extend(validation[:1 + outcomes[0]])
            if not perfect_validation:
                expected.extend(training[:1 + outcomes[2]])
            assert list(ledger) == [('incumbent', row.id) for row in expected]
            assert sum(value for key, value in audit.items() if key.endswith('Lookups')) == len(expected)
