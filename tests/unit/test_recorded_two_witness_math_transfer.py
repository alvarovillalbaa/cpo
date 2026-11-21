from benchmarks import recorded_two_witness_math_transfer as study


def test_matching_uses_distinct_lookup_and_historical_cost_units():
    totals = {arm: {'holdoutPasses': 4, 'paidLookups': 10, study.HISTORICAL: 50} for arm in study.METHODS}
    totals[study.RETAIN] = {'holdoutPasses': 2, 'paidLookups': 0, study.HISTORICAL: 0}
    totals['gepa/short'] = {'holdoutPasses': 6, 'paidLookups': 8, study.HISTORICAL: 52}
    totals['gepa/cheap'] = {'holdoutPasses': 5, 'paidLookups': 11, study.HISTORICAL: 48}
    vectors = {arm: [row['holdoutPasses']] for arm, row in totals.items()}
    plan = {'bootstrapDraws': 4, 'bootstrapSeed': 1}
    settings = ('gepa/short', 'gepa/cheap')

    lookup = study.matched(plan, totals, vectors, settings, 'paidLookups')[study.PRIMARY]
    historic = study.matched(plan, totals, vectors, settings, study.HISTORICAL)[study.PRIMARY]
    assert lookup['bestWithinCost'] == 'gepa/short'
    assert lookup['bestWithinCostPoint'] == totals['gepa/short']
    assert historic['bestWithinCost'] == 'gepa/cheap'
    assert historic['bestWithinCostPoint'] == totals['gepa/cheap']


def test_root_and_rotated_rosters_keep_the_original_disjoint_case_roles():
    cells = dict.fromkeys('abcde', (None,) * 13)
    settings = {'seeds': (31,), 'cohorts': (4, 3, 2, 4)}
    [root] = list(study.trials(cells, settings, 'root', 2))
    rotated = list(study.trials(cells, settings, 'rotated', 2))
    assert root[0] == 'a'
    assert [start for start, _, _, _ in rotated] == list('bcde')
    for start, roster, cases, seed in [root, *rotated]:
        assert start not in roster and len(set(roster)) == 2
        assert seed == 31
        assert cases == root[2]
        assert sorted(case for role in cases for case in role) == list(range(13))
