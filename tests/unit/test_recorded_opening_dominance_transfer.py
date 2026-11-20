"""Verify the paired replay charges search and admission only."""

from benchmarks.recorded_opening_dominance_transfer import BASELINE, CANDIDATE, trial


def test_archived_costs_charge_only_observed_search_and_admission_cells():
    cells = {
        'start': ((0, 1000, False), (0, 2, False), (0, 3, False), (0, 5, False), (1, 1000, False)),
        'rewrite': ((0, 1000, False), (1, 7, False), (0, 11, True), (1, 13, False), (0, 1000, False)),
        'repair': ((0, 1000, False), (0, 17, False), (0, 19, False), (0, 23, False), (0, 1000, False)),
    }
    cohorts = ((0,), (1, 2), (3,), (4,))
    pair = ('rewrite', 'repair')
    baseline = trial(cells, 'start', pair, cohorts, 7, BASELINE)
    certified = trial(cells, 'start', pair, cohorts, 7, CANDIDATE)
    assert certified['nominee'] == baseline['nominee'] == 'rewrite'
    assert certified['selected'] == baseline['selected'] == 'rewrite'
    assert certified['passed'] == baseline['passed'] == [0]
    assert certified['totals'] == {'holdoutPasses': 0, 'searchReads': 3, 'admissionReads': 2, 'paidReads': 5,
                                    'historicalCostNanodollars': 30, 'historicalErrors': 0}
    assert baseline['totals']['historicalCostNanodollars'] == 41
    assert baseline['totals']['historicalErrors'] == 1
