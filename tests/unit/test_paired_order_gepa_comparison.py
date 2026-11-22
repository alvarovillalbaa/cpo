import pytest

from benchmarks import paired_order_gepa_comparison as study


@pytest.mark.parametrize('mode', study.native_cost.MODES)
def test_paired_native_controls_keep_the_original_decisions_at_every_search_boundary(mode):
    pytest.importorskip('gepa')
    grades = {'start': (0,) * 10 + (1, 0, 0, 0, 0, 0) + (0, 1, 1, 0) + (0,) * 4,
              'next': (1,) * 24, 'other': (0,) * 24}
    cells = {name: tuple((grade, None, False) for grade in row) for name, row in grades.items()}
    cohorts = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 24)))
    args = cells, 'start', ('next', 'other'), cohorts, 7
    paths = study.native_paths(args, mode, 6, 48)
    for rule in study.RULES:
        original, paired = paths[rule], paths[f'paired-{rule}']
        assert paired.keys() == original.keys()
        for cap, (point, trace, held) in original.items():
            adjusted, after, grades = paired[cap]
            assert trace[:4] == after[:4]
            assert grades == held
            assert adjusted['searchLookups'] == point['searchLookups']
            assert adjusted['paidLookups'] == adjusted['searchLookups'] + adjusted['qualificationLookups']
            assert adjusted['qualificationLookups'] <= 8
        assert paired[48][1][3] == 'next'
