"""T2 synthetic forecasts that isolate each ranking component."""

from fractions import Fraction

import pytest

from benchmarks import continuous_backup_calibration as calibration
from benchmarks.continuous_backup_calibration_ablation import predict


@pytest.mark.parametrize('method', [calibration.EMPIRICAL, calibration.CORRECTED])
def test_replacing_one_forecast_factor_leaves_the_other_exact(method):
    samples = {'all': (100, 10, 250, 20_000_000, 400_000_000)}
    context = ('all', 'paid')
    baseline = Fraction(2, 5), Fraction(4)
    full = calibration.predict(method, samples, context, baseline, 6, 24)
    assert full[0] != baseline[0]
    assert full[1] != baseline[1]
    assert predict(f'{method}-probability', samples, context, baseline, 6, 24) == (full[0], baseline[1])
    assert predict(f'{method}-cost', samples, context, baseline, 6, 24) == (baseline[0], full[1])
