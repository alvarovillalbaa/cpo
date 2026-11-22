from benchmarks import recorded_paid_validation_continuation as study


def test_paid_tie_can_continue_and_reuses_the_full_pool_path():
    arguments = episode((0, 1, 1, 0, 0, 0))
    full = study.prior.fitted.cpo_trial(arguments, study.prior.POLICY, study.FULL)
    assert full[1][3] == 'later'
    assert study.routed_trial(arguments, study.PAID) == (full, True)
    assert study.routed_trial(arguments, study.BLIND) == (full, True)


def test_unread_candidates_cannot_trigger_paid_continuation():
    arguments = episode((1, 1, 0, 0, 0, 0))
    low = study.prior.fitted.cpo_trial(arguments, study.prior.POLICY, study.LOW)
    full = study.prior.fitted.cpo_trial(arguments, study.prior.POLICY, study.FULL)
    assert low[1][3] == 'start'
    assert full[1][3] == 'later'
    assert study.routed_trial(arguments, study.PAID) == (low, False)
    assert study.routed_trial(arguments, study.BLIND) == (full, True)


def episode(first_validation):
    splits = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 25)))
    scores = {'start': (1, 1, 0, 0, 0, 0), 'first': first_validation, 'later': (1,) * 6}
    cells = {prompt: [(value, None, False) for value in
                      (0,) * 10 + validation + (int(prompt == 'later'),) * 9]
             for prompt, validation in scores.items()}
    return cells, 'start', ['first', 'later'], splits, 7
