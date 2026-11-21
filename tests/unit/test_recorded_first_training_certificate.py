from itertools import product

from benchmarks import recorded_first_training_certificate as study
from cpo import Observation, Row


def test_every_certificate_preserves_incumbent_critical_passes_and_proves_strict_gain():
    validation = (Row('a', 'validation', True), Row('b', 'validation'), Row('c', 'validation'))
    training = (Row('training', 'training'),)
    names = ('start', 'a', 'b')
    keys = tuple((prompt, row.id) for prompt in names for row in validation)
    for bits in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, bits, strict=True))
        ledger = {}

        def read(prompt, row):
            cell = prompt, row.id
            assert cell not in ledger
            ledger[cell] = Observation(grades[cell], {})
            return ledger[cell]

        certificates = list(study.certificates(names[0], names[1:], validation, training, read, ledger, 11))
        expected = [prompt for prompt in names[1:]
                    if sum(grades[prompt, row.id] for row in validation) > sum(bits[:3])
                    and (not grades['start', 'a'] or grades[prompt, 'a'])]
        assert [prompt for prompt, _ in certificates] == expected
        for prompt, _ in certificates:
            assert sum(reply.passed for (owner, _), reply in ledger.items() if owner == prompt) > sum(bits[:3])
        assert len(ledger) <= 9


def test_race_stops_at_a_certificate_and_reserves_the_training_check():
    training = (Row('training', 'training'),)
    validation = tuple(Row(str(index), 'validation') for index in range(3))
    ledger = {}

    def read(prompt, row):
        ledger[prompt, row.id] = Observation(prompt != 'start', {})
        return ledger[prompt, row.id]

    assert not list(study.certificates('start', ('candidate',), validation, training, read, ledger, 7))
    assert all(prompt == 'start' for prompt, _ in ledger)
    ledger.clear()
    stream = study.certificates('start', ('candidate', 'backup'), validation, training, read, ledger, 9)
    assert next(stream) == ('candidate', 1)
    assert not any(prompt == 'backup' for prompt, _ in ledger)
    assert next(stream) == ('backup', 1)
