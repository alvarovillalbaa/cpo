from itertools import product

from benchmarks import recorded_expected_training_order as study
from cpo import Observation, Row


def test_estimated_price_can_change_the_next_read_without_changing_the_threshold():
    assert study.next_side((2, 2), (3, 1), (1, 1), 1)[1] == 1
    assert study.next_side((2, 2), (1, 3), (1, 1), 1)[1] == 0
    assert study.next_side((2, 2), (3, 1), (1, 1), 3) == (0, None)


def test_every_small_training_board_settles_the_exact_gain_with_or_without_paid_prefix():
    prompts = ('old', 'new')
    rows = tuple(Row(str(case), 'training') for case in range(3))
    keys = tuple((prompt, row.id) for prompt in prompts for row in rows)
    for outcomes in product((False, True), repeat=len(keys)):
        board = dict(zip(keys, outcomes, strict=True))
        expected = sum(outcomes[3:]) > sum(outcomes[:3])
        for cached in ((), keys[:2], keys[2:5]):
            ledger = {key: Observation(board[key], {}) for key in cached}
            observed = set()

            def evaluate(prompt, row):
                key = prompt, row.id
                assert key not in ledger and key not in observed
                observed.add(key)
                return Observation(board[key], {})

            assert study.settle(prompts, rows, evaluate, ledger, (1, 3), (2, 7), minimum_gain=1) == expected
            assert len(observed) <= len(keys) - len(cached)
