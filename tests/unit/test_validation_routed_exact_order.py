from itertools import product

from benchmarks.validation_routed_exact_order import exact_screen
from cpo import Observation, Row
from cpo.ordered_uniform_validation import MISSES, screen as ordered_screen


def test_prepaid_and_paired_orders_preserve_every_four_row_decision():
    prompts = ('base', 'first', 'second')
    rows = tuple(Row(str(index), 'validation') for index in range(4))
    for grades in product((False, True), repeat=len(prompts) * len(rows)):
        table = dict(zip(product(prompts, rows), grades, strict=True))
        opening = rows[:2] if table['base', rows[0]] else rows[:1]
        prepaid = {row.id for row in opening}
        outputs = []
        for mode in ('original', 'prepaid', 'paired'):
            paid = []

            def evaluate(prompt, row):
                assert (prompt, row) not in paid
                paid.append((prompt, row))
                return Observation(table[prompt, row], {})

            args = prompts[0], prompts[1:], rows, evaluate, 12
            if mode == 'original':
                result, counts = ordered_screen(*args, order=MISSES)
            else:
                result, counts = exact_screen(*args, prepaid=prepaid, paired=mode == 'paired')
                assert paid[:len(opening)] == [('base', row) for row in opening]
            assert result.evaluations == len(paid) <= 12
            outputs.append((result.prompt, result.finalist, counts))
        assert outputs[0] == outputs[1] == outputs[2]
