from benchmarks.first_gain_tail_paired_audit import CANDIDATES, affordable, paired, transfer


def test_paired_draws_keep_every_repeat_of_a_question_together():
    vectors = {'candidate': (7, 0), 'control': (0, 0), 'same': (7, 0)}
    matches = {'difference': ('candidate', ('control',)), 'identity': ('candidate', ('same',))}
    result = paired(vectors, matches, draws=512, seed=1)
    assert result['difference'] == {'passDelta': 7, 'caseResampled95': [0, 14], 'comparedSettings': 1}
    assert result['identity'] == {'passDelta': 0, 'caseResampled95': [0, 0], 'comparedSettings': 1}


def test_draws_reselect_strongest_affordable_control():
    vectors = {'candidate': (1, 1), 'left': (2, 0), 'right': (0, 2)}
    matches = {'menu': ('candidate', ('left', 'right')), 'one': ('candidate', ('left',))}
    result = paired(vectors, matches, draws=512, seed=1)
    assert result['menu'] == {'passDelta': 0, 'caseResampled95': [-2, 0], 'comparedSettings': 2}
    assert result['one']['caseResampled95'] == [-2, 2]


def test_receipt_admits_every_control_affordable_on_either_cost_axis():
    def costs(lookups, price):
        return {'paidLookups': lookups, 'price': price}

    reference = {'arms': {CANDIDATES[0]: {'totals': costs(5, 2)}, CANDIDATES[1]: {'totals': costs(6, 3)}}}
    published = {transfer.BASE: costs(0, 0), 'gepa-a': costs(6, 8), 'halving/a': costs(8, 3),
                 'gepa-b': costs(7, 4), 'unrelated': costs(1, 1)}
    assert affordable(published, reference, ('paidLookups', 'price')) == (transfer.BASE, 'gepa-a', 'halving/a')
