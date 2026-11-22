from unittest.mock import patch

import pytest

from benchmarks import recorded_matched_qualification_margin as study


@pytest.mark.parametrize('mode', study.cost.MODES)
def test_stronger_gepa_proof_keeps_search_and_matches_direct_caps(mode):
    pytest.importorskip('gepa')
    grades = {'start': (0,) * 10 + (1, 0, 0, 0, 0, 0) + (0,) * 4 + (0,) * 4,
              'challenger': (1,) * 16 + (1, 0, 0, 0) + (1,) * 4,
              'other': (0,) * 10 + (1, 1, 1, 0, 0, 0) + (0,) * 8}
    cells = {name: [(grade, None, False) for grade in row] for name, row in grades.items()}
    cohorts = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 24)))
    args = cells, 'start', ('challenger', 'other'), cohorts, 7
    baseline, stronger = study.native_paths(args, mode, 6, 40)
    assert baseline[40][1][2:4] == ('challenger', 'challenger')
    assert stronger[40][1][2:4] == ('challenger', 'start')
    with patch.object(study.cost.adapter, 'qualify_with_prefix', study.prior.minimum_two):
        for cap in range(6, 41):
            preceding = max(boundary for boundary in stronger if boundary <= cap)
            assert study.cost.run(args, mode, cap) == stronger[preceding]
