from benchmarks import witness_training_context as study


def test_stress_cases_are_fresh_and_cover_every_declared_context():
    groups = study.EPISODE.cohorts()
    panels = study.stress_cases(groups)

    for task, rows in panels.items():
        assert [study.context(task, row) for row in rows] == list(study.CONTEXTS[task])
        assert len({row['input'] for row in rows}) == len(rows)
        assert {row['input'] for row in rows}.isdisjoint(
            row['input'] for split in groups[task].values() for row in split)


def test_pair_and_context_selectors_cover_their_declared_training_features():
    rows = study.EPISODE.cohorts()['warehouse']['train'][:study.EPISODE.TRAIN_ROWS]

    for full in (False, True):
        selected = study.parent.minimum_cover(rows, lambda row: study.features('warehouse', row, full=full))
        base = set().union(*(study.features('warehouse', row, full=full) for row in rows))
        exact = set().union(*(study.features('warehouse', row, full=full) for row in selected))
        assert exact == base


def test_independent_faults_only_change_the_diagnostics():
    groups = study.EPISODE.cohorts()
    regions = groups['outage']
    reference = study.parent.compare('outage', regions)
    real = study.measure('outage', regions, study.stress_cases(groups)['outage'], reference)
    empty = study.measure('outage', {**regions, 'holdout': [], 'confirmation': []}, [], reference)

    for observed, removed in zip(real, empty, strict=True):
        for policy in study.NAMES:
            assert observed[policy]['cases'] == removed[policy]['cases']
        assert observed['completeContexts']['lostObservedContexts'] == []
        assert all(row['lostCases'] == 0 for row in observed['completeContexts']['scoring'].values())
