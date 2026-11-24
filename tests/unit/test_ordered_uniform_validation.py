from itertools import product

from cpo import Observation, Row
from cpo.ordered_uniform_validation import MISSES, ORDERS, ORIGINAL, PASSES, run_ordered_uniform_cycle, screen
from cpo.quoted_shared_validation_cycle import _schedule


ROWS = tuple(Row(str(i), 'validation') for i in range(3))
ROSTER = ('a', 'b', 'c')


def check(order, grades, cap, rows=ROWS):
    ledger = []

    def evaluate(prompt, row):
        assert (prompt, row) not in ledger
        ledger.append((prompt, row))
        return Observation(grades[prompt, row], {})

    result, counts = screen('base', ROSTER, rows, evaluate, cap, order=order)
    assert len(ledger) == result.evaluations <= cap
    return (result.prompt, result.finalist, counts), ledger


def test_every_three_case_panel_preserves_exact_scores_and_funded_cases():
    cells = tuple(product(('base', *ROSTER), ROWS))
    for outcomes in product((False, True), repeat=len(cells)):
        grades = dict(zip(cells, outcomes, strict=True))
        for cap in (0, 4, 8, 12):
            old, _ = check(ORIGINAL, grades, cap)
            funded = {row for row, _ in _schedule(len(ROSTER), ROWS, cap, False)}
            for order in (MISSES, PASSES):
                result, ledger = check(order, grades, cap)
                assert result == old
                assert {row for _, row in ledger} <= funded


def test_miss_first_can_save_reads_or_increase_them():
    for misses_align in (False, True):
        grades = {(prompt, row): row == ROWS[int(prompt != 'base' and not misses_align)]
                  for prompt, row in product(('base', *ROSTER), ROWS)}
        original, old_reads = check(ORIGINAL, grades, 8)
        changed, reads = check(MISSES, grades, 8)
        assert changed == original
        assert len(reads) - len(old_reads) == (-3 if misses_align else 3)
        assert reads[:2] == [('base', row) for row in ROWS[:2]]


def test_critical_panel_uses_identical_paid_path_and_qualification():
    critical = Row('guard', 'validation', critical=True)
    rows = (critical, *ROWS[:2])

    def run(order):
        ledger = []

        def evaluate(prompt, row):
            ledger.append((prompt, row))
            return Observation(prompt == 'a' or (prompt == 'base' and row == critical), {})

        result = run_ordered_uniform_cycle('base', ROSTER, rows, (Row('q', 'qualification'),), evaluate,
                                           metric_limit=12, qualify=lambda prompt, *_: prompt == 'a', order=order)
        return result, ledger

    original = run(ORIGINAL)
    assert original[0].prompt == 'a'
    for order in ORDERS:
        assert run(order) == original
