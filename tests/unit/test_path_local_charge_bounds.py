"""Verify the bundled cost proof and its source binding."""

from hashlib import sha256
import json

import pytest

from benchmarks.path_local_charge_bounds import DATA, FIXED, measure, read_terms


def test_bundled_path_terms_reproduce_the_full_archive_receipt():
    data = read_terms(DATA.read_bytes())
    report = measure(data, FIXED.read_bytes())
    assert report['pooled']['paths'] == 240
    assert report['pooled']['chargeAwareVersusNative']['separateChargeSavingsFractionIsTight']
    assert report['pooled']['tenPercentGateHeadroom']['additionalMarginVersusRowPairedMicrousd'] == '588168'
    encoded = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    assert sha256(encoded).hexdigest() == data['archiveAuditSha256'] == (
        '863a2877f0372f80a6d2165d66dab158f40aa8fb4f37e4e02416d1c7a340bfab')


def test_path_terms_reject_a_different_row_paired_reference():
    data = read_terms(DATA.read_bytes())
    with pytest.raises(ValueError, match='versioned path and row-paired charge terms'):
        measure(data, FIXED.read_bytes() + b'\n')
