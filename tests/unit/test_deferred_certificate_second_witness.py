from benchmarks.deferred_certificate_second_witness import GAIN_DEFER, RETAIN_DEFER, RETAIN_FIRST, run_trial


CELLS = {'start': (0, 0, 1, 1, 0, 0), 'first': (1, 1, 0, 1, 1, 0), 'next': (1, 1, 1, 0, 1, 1)}
ROLES = (), (0, 1, 2, 3), (4,), (5,)


def test_paid_retention_miss_can_change_priority_at_the_same_cap():
    args = CELLS, 'start', ('first', 'next'), ROLES, 0, 9, 1
    control, _ = run_trial(RETAIN_FIRST, args)
    gains, _ = run_trial(GAIN_DEFER, args)
    retention, paid = run_trial(RETAIN_DEFER, args)

    assert control.prompt == gains.prompt == 'first'
    assert retention.prompt == 'next'
    assert retention.search.evaluations == 9
    assert [key for key in paid if key[0] == 'validation' and key[1] != 'start'] == [
        ('validation', 'first', '0'), ('validation', 'first', '2'), ('validation', 'next', '0'),
        ('validation', 'next', '2'), ('validation', 'next', '1'),
    ]


def test_deferred_challenger_remains_eligible_and_reuses_both_paid_witnesses():
    cells = {**CELLS, 'next': (0, 1, 1, 0, 1, 1)}
    result, paid = run_trial(RETAIN_DEFER, (cells, 'start', ('first', 'next'), ROLES, 0, 9, 1))

    assert result.prompt == 'first'
    assert result.search.evaluations == 9
    assert [key for key in paid if key[0] == 'validation' and key[1] != 'start'] == [
        ('validation', 'first', '0'), ('validation', 'first', '2'), ('validation', 'next', '0'),
        ('validation', 'first', '1'), ('validation', 'first', '3'),
    ]
