from itertools import product

from benchmarks.qualification_after_stalled_validation import TIE, TRAINING, certify_nonloss, execute_trial
from cpo import Row


def test_witnessed_validation_tie_can_qualify_once_without_training():
    cells = {'start': (0, 0, 1, 0, 1, 0, 0, 0), 'rival': (1, 1, 0, 1, 1, 1, 1, 1)}
    roles = (0, 1), (2, 3, 4), (5, 6), (7,)
    result, paid = execute_trial(cells, 'start', ('rival',), roles, 19, 10, 1, TIE)

    assert result.prompt == 'rival'
    assert paid['validation', 'start', '3'] is False
    assert paid['validation', 'rival', '3'] is True
    assert all(role != 'training' for role, _, _ in paid)
    assert result.qualification_evaluations <= 4


def test_disjoint_training_can_nominate_after_a_validation_loss():
    cells = {'start': (0, 0, 1, 0, 1, 0, 0, 0), 'rival': (1, 1, 0, 0, 1, 1, 1, 1)}
    roles = (0, 1), (2, 3, 4), (5, 6), (7,)
    result, paid = execute_trial(cells, 'start', ('rival',), roles, 19, 10, 1, TRAINING)

    assert result.prompt == 'rival'
    assert {int(case) for role, _, case in paid if role == 'training'} <= {0, 1}
    assert result.search.evaluations <= 10
    assert result.qualification_evaluations <= 4


def test_exact_nonloss_rejects_losses_and_requests_no_more_than_its_allowance():
    rows = (Row('0', 'validation'), Row('1', 'validation'))
    for grades, allowance in product(product((False, True), repeat=4), range(5)):
        observed = set()

        def read(side, row):
            key = side, row.id
            assert key not in observed
            observed.add(key)
            return grades[2 * side + int(row.id)]

        exact = certify_nonloss(rows, {}, {}, read, allowance)
        expect = sum(grades[2:]) >= sum(grades[:2])
        assert len(observed) <= allowance
        if exact or allowance == 4:
            assert exact == expect
