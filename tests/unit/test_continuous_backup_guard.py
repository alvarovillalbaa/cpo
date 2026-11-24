"""T2 paid-grade fixtures for the backup preservation gate and quote."""

from fractions import Fraction

from benchmarks.continuous_archive_backup import Opportunity
from benchmarks.continuous_backup_guard import CACHED, ONE, TWO, Offer, attempt, guard_options
from cpo.optimizer import Row
from cpo.paired_qualification import QualificationObservation


def test_preservation_evidence_and_probe_limits_follow_paid_validation_only():
    cached = Opportunity('cached', 'miss', ((1, 2), (2, 2)), 5, Fraction(1, 4))
    repair = Opportunity('repair', None, ((1, 2), (1, 1)), 4, Fraction(1, 5))
    pending = Opportunity('pending', 'miss', ((1, 2), (1, 1)), 5, Fraction(1, 6))
    paid = {('validation', 'base', 'pass'): True, ('validation', 'base', 'miss'): False,
            ('validation', 'cached', 'pass'): True, ('qualification', 'pending', 'pass'): True}
    args = (cached, repair, pending), 'base', paid
    assert guard_options(CACHED, *args) == [Offer(cached, None)]
    assert guard_options(ONE, *args) == [Offer(cached, None), Offer(repair, 'pass')]
    assert guard_options(TWO, *args) == [Offer(cached, None), Offer(repair, 'pass'), Offer(pending, 'pass')]


def test_both_validation_reads_are_reserved_and_failed_guard_prevents_proof():
    option = Opportunity('backup', 'miss', ((1, 2), (1, 1)), 2, Fraction(1, 4))
    offer = Offer(option, 'pass')
    first = (QualificationObservation('base', 'q', 0, False),)
    rows = (Row('q', 'qualification'),)
    events = []

    def run(limit, repair_passed, retained):
        def acquire(role, prompt, row):
            events.append((role, prompt, row))
            return {'miss': repair_passed, 'pass': retained, 'q': True}[row]

        return attempt(offer, 'base', rows, first, acquire, limit, 0, {None: (1, 1, 1, 1)})

    assert run(2, True, True) == ('base', (), 'unfunded')
    assert events == []
    assert run(3, False, True)[2] == 'no-repair'
    assert events == [('validation', 'backup', 'miss')]
    events.clear()
    assert run(3, True, False)[2] == 'guard-rejected'
    assert events == [('validation', 'backup', 'miss'), ('validation', 'backup', 'pass')]
    events.clear()
    assert run(3, True, True)[0] == 'backup'
    assert events == [('validation', 'backup', 'miss'), ('validation', 'backup', 'pass'),
                      ('qualification', 'backup', 'q')]
