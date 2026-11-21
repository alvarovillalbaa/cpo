from itertools import product

from benchmarks import recorded_two_witness_arc_cost_order as study
from cpo import Observation, Row, select_pool


def test_price_order_preserves_full_pool_nomination_for_every_three_by_three_board():
    names = ('start', 'first', 'second')
    rows = tuple(Row(str(index), 'validation', index == 1) for index in range(3))

    def priced_cost(name, row):
        return (names.index(name) + 1) * (int(row.id) + 2)

    for flags in product((False, True), repeat=9):
        board = dict(zip(((name, row.id) for name in names for row in rows), flags, strict=True))
        calls = set()

        def evaluate(prompt, row):
            key = prompt, row.id
            assert key not in calls
            calls.add(key)
            return board[key], priced_cost(prompt, row)

        result, paid = study.select_by_paid_cost('start', names[1:], rows, evaluate, cap=9)
        original = select_pool(names, rows, lambda prompt, row: Observation(board[prompt, row.id], {}),
                               metric_limit=9, adaptive_rejection=True)
        assert result == original.prompt
        assert paid == len(calls) <= 9
