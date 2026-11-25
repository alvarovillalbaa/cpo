from benchmarks import full_roster_precheck_math as study


def test_math_transfer_only_shortens_the_qualification_panel():
    plan, archive = study.prepare()
    for subject, settings in plan['datasets'].items():
        cells = study.math.load_cells(subject, archive[subject]['record'])
        expected = study.math_transfer.prior.trials(cells, settings, 'root', 8)
        adapted = study.four_case_trials(cells, settings, 'root', 8)
        for original, trial in zip(expected, adapted, strict=True):
            start, roster, (train, validation, admission, held), seed = original
            assert trial == (start, roster, (train, validation, admission[:4], held), seed)


def test_full_roster_lookup_and_recorded_price_reconcile_per_reply():
    roster = tuple(f'candidate-{index}' for index in range(8))
    trial = 'base', roster, ([0, 1, 2], [3, 4, 5], [6, 7, 8, 9], [10]), 1
    baseline = tuple((int(index in {0, 3, 4, 5, 10}), 5 + index, False) for index in range(11))
    archive = {'base': baseline, **{prompt: baseline for prompt in roster}}
    feedback, guarded = (study.episode(runner, archive, trial) for runner in study.RUNNERS.values())
    assert feedback[0].prompt == guarded[0].prompt == 'base'
    assert feedback[2] == guarded[2] == [1]
    assert feedback[1]['paidLookups'] == guarded[1]['paidLookups'] + 1
    assert feedback[1][study.HISTORICAL] == guarded[1][study.HISTORICAL] + 11
    assert {role for role, *_ in guarded[3]} == {'training', 'validation'}
