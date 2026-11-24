"""T2 mock grades for the terminal archive backup reservation and proof."""

from fractions import Fraction

from benchmarks.continuous_archive_backup import PAID, PROBE, REPAIR, attempt, nominate, qualification_value
from cpo.optimizer import Row
from cpo.paired_qualification import QualificationObservation


PRIORS = {None: (1, 1, 1, 1)}


def test_single_probe_can_open_fresh_candidate_and_never_reopens_rejected_nominee():
    initial = (QualificationObservation('base', 'q0', 0, False),)
    paid = {('validation', 'base', 'v0'): False, ('validation', 'base', 'v1'): True,
            ('validation', 'rejected', 'v0'): True}
    args = 'base', ('rejected', 'alternate'), 'rejected', 2, 2, paid, initial, PRIORS
    assert not nominate(PAID, *args)
    assert not nominate(REPAIR, *args)
    option, = nominate(PROBE, *args)
    assert (option.candidate, option.validation_probe, option.price) == ('alternate', 'v0', 4)

    callbacks = []

    def acquire(role, prompt, row):
        callbacks.append((role, prompt, row))
        assert role == 'validation'
        return False

    rows = (Row('q0', 'qualification'), Row('q1', 'qualification'))
    assert attempt(option, 'base', rows, initial, acquire, 3, 0, PRIORS) == ('base', (), 'unfunded')
    assert not callbacks
    result, ledger, status = attempt(option, 'base', rows, initial, acquire, 4, 0, PRIORS)
    assert (result, ledger, status) == ('base', (('validation', 'alternate', 'v0', False),), 'no-repair')


def test_backup_reuses_paid_incumbent_and_requires_independent_gain():
    rows = (Row('q0', 'qualification'), Row('q1', 'qualification'))
    initial = (QualificationObservation('base', 'q0', 0, False),
               QualificationObservation('base', 'q1', 0, True))
    paid = {('validation', 'base', 'v0'): False, ('validation', 'base', 'v1'): True,
            ('validation', 'alternate', 'v0'): True}
    args = 'base', ('alternate',), 'rejected', 2, 2, paid, initial, PRIORS
    assert not nominate(PAID, *args)
    option, = nominate(REPAIR, *args)
    assert option.price == 2 and option.validation_probe is None
    scenarios = (({'q0': True, 'q1': True}, 'alternate', 2), ({'q0': True, 'q1': False}, 'base', 1))
    for grades, expected, reads in scenarios:
        def acquire(role, prompt, row):
            assert (role, prompt) == ('qualification', 'alternate')
            return grades[row]

        result, ledger, _ = attempt(option, 'base', rows, initial, acquire, 2, 0, PRIORS)
        assert result == expected
        assert len(ledger) == reads


def test_factorized_prior_matches_known_small_proof_probability_and_cost():
    assert qualification_value(PRIORS[None], 1, 0, 1) == (Fraction(1, 2), Fraction(5, 2))
