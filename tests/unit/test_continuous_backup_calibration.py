"""T2 fixtures for exact forecast factoring and empirical calibration."""

from fractions import Fraction

from benchmarks.continuous_archive_backup import Opportunity
from benchmarks.continuous_backup_calibration import CORRECTED, EMPIRICAL, forecast, predict
from cpo.paired_qualification import QualificationObservation


def test_factors_original_probability_and_pays_failed_probe_in_expected_cost():
    priors = {None: (1, 1, 1, 1)}
    initial = (QualificationObservation('base', 'a', 0, False),)
    option = Opportunity('backup', 'miss', ((0, 1), (1, 1)), 4, Fraction(1, 9))
    assert forecast(option, 2, initial, priors) == (Fraction(1, 4), Fraction(9, 4))


def test_missing_calibration_context_inherits_and_correction_keeps_individual_information():
    samples = {'all': (100, 25, 200, 25_000_000, 200_000_000)}
    context = ('all', 'unseen')
    baseline = Fraction(1, 2), Fraction(3)
    assert predict(EMPIRICAL, samples, context, baseline, 5, 24) == (Fraction(1, 4), Fraction(2))
    assert predict(CORRECTED, samples, context, baseline, 5, 24) == baseline


def test_estimated_charge_is_bounded_by_the_full_quote():
    samples = {'all': (100, 20, 400, 10_000_000, 200_000_000)}
    probability, charge = predict(CORRECTED, samples, ('all',), (Fraction(3, 4), Fraction(3)), 4, 24)
    assert 0 <= probability <= 1
    assert charge == 4
