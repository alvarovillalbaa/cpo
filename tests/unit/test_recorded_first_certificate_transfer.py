from benchmarks import recorded_first_certificate_transfer as study


def test_transfer_keeps_the_existing_holdout_and_pairs_both_model_panels():
    plan, panels = study.prepare()
    assert len(panels) == 26
    assert len({(cohort, subject) for cohort, subject, _, _ in panels}) == 13
    assert plan['caseCounts'] == (10, 6, 4)
    aligned = {}
    for cohort, subject, _, matrix in panels:
        start, roster, groups = study.schedule(subject, len(matrix[0]), len(matrix), plan['seeds'][0], plan)
        assert len({start, *roster}) == 9
        assert tuple(map(len, groups[:3])) == plan['caseCounts']
        assert sum(map(len, groups)) == len({case for part in groups for case in part})
        assert groups[-1] == study.source.holdout(subject, len(matrix[0]))
        layout = start, roster, groups
        assert aligned.setdefault((cohort, subject), layout) == layout


def test_paired_gate_checks_the_weaker_control_and_the_cheaper_control():
    first, *_, retained = study.METHODS
    sequential, batched = study.CONTROL_NAMES.values()
    plan = {'bootstrapSeed': 5, 'bootstrapDraws': 64, 'minimumLookupSavingPercent': 10}
    cost = {arm: {'paidLookups': lookups} for arm, lookups in ((first, 80), (sequential, 100), (batched, 90))}
    vector = {'one': {first: [3, 3], sequential: [2, 2], batched: [3, 3], retained: [1, 1],
                      study.study.prior.CANDIDATE: [3, 3]}}
    assert study.compare(plan, cost, vector)['gate'] == 'passed'
    cost[first]['paidLookups'] = 82
    assert study.compare(plan, cost, vector)['gate'] == 'failed'
    cost[first]['paidLookups'] = 80
    vector['one'][batched] = [4, 4]
    assert study.compare(plan, cost, vector)['caseSensitivityRanges']['joint'] == [-2, -2]
    assert study.compare(plan, cost, vector)['gate'] == 'failed'
