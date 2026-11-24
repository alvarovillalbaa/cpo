"""T2 paid-grade fixtures for single-probe witness selection."""

from fractions import Fraction

from benchmarks import continuous_archive_backup as backup
from benchmarks.continuous_backup_witness import (
    COMPLEMENT, LAST, PEERS, adjust_priority, choose_witness, peer_counts, priced_bounds, unread_misses,
)
from cpo.paired_qualification import QualificationObservation


def test_witness_ranking_uses_only_paid_validation_and_unread_incumbent_misses():
    paid = {
        ('validation', 'base', 'v1'): False,
        ('validation', 'base', 'v2'): False,
        ('validation', 'base', 'v3'): True,
        ('validation', 'base', 'v4'): False,
        ('validation', 'candidate', 'v4'): False,
        ('validation', 'previous', 'v1'): False,
        ('validation', 'previous', 'v2'): True,
        ('qualification', 'peer', 'v1'): True,
        ('validation', 'other-peer', 'v2'): True,
    }
    assert unread_misses('base', 'candidate', paid) == ['v1', 'v2']
    assert peer_counts('v1', paid, 'base', 'candidate') == (0, 1)
    assert choose_witness(PEERS, 'base', 'candidate', 'previous', paid) == 'v2'
    assert choose_witness(COMPLEMENT, 'base', 'candidate', 'previous', paid) == 'v1'
    assert choose_witness(LAST, 'base', 'candidate', 'previous', paid) == 'v2'


def test_row_specific_probe_estimate_falls_back_and_updates_in_the_observed_direction():
    priors = {None: (1, 1, 1, 1)}
    initial = (QualificationObservation('base', 'q0', 0, False),)
    option = backup.Opportunity('candidate', 'v1', ((0, 1), (1, 1)), 4, Fraction(1, 9))
    paid = {('validation', 'base', 'v1'): False}
    baseline = adjust_priority(option, 'v1', 'base', 2, paid, initial, priors)
    assert baseline == Fraction(1, 9)
    assert adjust_priority(option, 'v1', 'base', 2, {**paid, ('validation', 'peer', 'v1'): True},
                           initial, priors) > baseline
    assert adjust_priority(option, 'v1', 'base', 2, {**paid, ('validation', 'peer', 'v1'): False},
                           initial, priors) < baseline


def test_settled_cost_frontier_distinguishes_total_charge_from_reserve_at_dispatch():
    groups = (((5, 2, 5),), ((7, 2, 4),))
    assert priced_bounds(groups, 5) == {'settledChargeUpperBound': 12, 'fullyReservedLowerBound': 7}
    assert priced_bounds(groups, 7) == {'settledChargeUpperBound': 12, 'fullyReservedLowerBound': 12}
