import pytest

from cpo import Row
from cpo.validation import sample_validation_panel


ROWS = [Row(str(index), 'routing', index < 8) for index in range(12)]
STRATA = {str(index): 'legacy' if index < 6 else 'interaction' for index in range(8)}


def test_stratification_covers_sparse_risk_and_preserves_the_ordinary_sample():
    regular = sample_validation_panel(ROWS, size=4, critical_count=2, seed=8)
    stratified = sample_validation_panel(ROWS, size=4, critical_count=2, critical_strata=STRATA, seed=8)
    assert {STRATA[row.id] for row in stratified if row.critical} == {'legacy', 'interaction'}
    assert sum(row.critical for row in stratified) == 2
    assert [row for row in regular if not row.critical] == [row for row in stratified if not row.critical]
    assert stratified == sample_validation_panel(ROWS, size=4, critical_count=2, critical_strata=STRATA, seed=8)


def test_impossible_quota_and_incomplete_strata_fail_before_selecting():
    with pytest.raises(ValueError, match='cannot meet both quotas'):
        sample_validation_panel(ROWS, size=7, critical_count=1)
    with pytest.raises(ValueError, match='declared stratum'):
        sample_validation_panel(ROWS, size=4, critical_count=2, critical_strata={'0': 'legacy'})
    with pytest.raises(ValueError, match='distinct row IDs'):
        sample_validation_panel([ROWS[0], *ROWS], size=4, critical_count=2)
