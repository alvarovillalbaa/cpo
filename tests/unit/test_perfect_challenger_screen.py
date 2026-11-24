from functools import partial
from itertools import product

from cpo import Observation, Row
from cpo.perfect_challenger_screen import run_perfect_challenger_cycle, screen
from cpo.quoted_shared_validation_cycle import _screen as original
from cpo.quoted_shared_validation_cycle import run_quoted_shared_validation_cycle


ROSTER = ('a', 'b', 'c')
ROWS = tuple(Row(str(index), 'validation') for index in range(3))


def run(method, grades, cap, rows=ROWS):
    ledger = set()

    def read(prompt, row):
        cell = prompt, row
        assert cell not in ledger
        ledger.add(cell)
        return Observation(grades[cell], {})

    result, counts = method('base', ROSTER, rows, read, cap)
    assert len(ledger) == result.evaluations <= cap
    return (result.prompt, result.finalist, counts), ledger


def test_every_small_binary_panel_preserves_choices_with_a_subset_of_the_reads():
    cells = tuple(product(('base', *ROSTER), ROWS))
    for values in product((False, True), repeat=len(cells)):
        grades = dict(zip(cells, values, strict=True))
        for halve, cap in product((False, True), (3, 4, 7, 9, 12)):
            before, paid = run(partial(original, halve=halve), grades, cap)
            after, kept = run(partial(screen, halve=halve), grades, cap)
            assert after == before
            assert kept <= paid


def test_first_perfect_contender_skips_later_hypotheses_and_keeps_qualification():
    def verify(cycle):
        reads = []

        def observe(prompt, row):
            reads.append((prompt, row))
            return Observation(prompt != 'base' or row == ROWS[0], {})

        result = cycle('base', ROSTER, ROWS[:2], (Row('q', 'qualification'),), observe,
                       metric_limit=8, qualify=lambda prompt, *_: prompt == 'a', schedule='uniform')
        return result, reads

    before, old_reads = verify(run_quoted_shared_validation_cycle)
    after, reads = verify(run_perfect_challenger_cycle)
    assert after.prompt == before.prompt == 'a'
    assert after.qualification == before.qualification
    assert reads == [('base', row) for row in ROWS[:2]] + [('a', row) for row in ROWS[:2]]
    assert len(reads) < len(old_reads)
