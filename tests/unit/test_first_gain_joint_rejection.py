from itertools import product

import pytest

from benchmarks.first_gain_joint_rejection import qualify_joint


def test_validation_rejection_removes_a_qualifying_contender_from_proof():
    grades = ((True, True, False), (False, True, False),
              (False, True, False), (False, True, False))
    initial = [(2, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 0)]
    paid = set()

    def observe(side, index):
        assert side != 1
        assert (side, index) not in paid
        paid.add((side, index))
        return grades[index][side]

    assert qualify_joint(initial.copy(), (1,), 12, observe)
    assert paid
    assert not qualify_joint(initial.copy(), (), 12, lambda side, index: grades[index][side])


@pytest.mark.parametrize('blocked', ((), (1,), (2,)))
def test_all_four_row_boards_produce_only_sound_rejections(blocked):
    certificates = handoffs = 0
    for grades in product(tuple(product((False, True), repeat=3)), repeat=4):
        board = [(0, 0, 0)] * 4
        for index, row in enumerate(grades):
            board[index] = (1 + row[0], 0, 0)
            if not row[0]:
                break

        def observe(side, index):
            assert board[index][side] == 0
            assert side not in blocked
            return grades[index][side]

        if qualify_joint(board, blocked, 8, observe):
            passes = tuple(sum(column) for column in zip(*grades))
            assert all(passes[side] <= passes[0] for side in (1, 2) if side not in blocked)
            certificates += 1
        else:
            handoffs += 1
    assert certificates and handoffs
