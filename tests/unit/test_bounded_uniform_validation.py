from itertools import product

from cpo import Observation, Row
from cpo.bounded_uniform_validation import screen
from cpo.quoted_shared_validation_cycle import _screen as quoted, _schedule


ROSTER = ('a', 'b', 'c')
ROWS = tuple(Row(str(index), 'validation') for index in range(3))


def run(method, grades, cap, *, rows=ROWS, halve=False):
    paid = set()

    def observe(prompt, row):
        cell = prompt, row
        assert cell not in paid
        paid.add(cell)
        return Observation(grades[cell], {})

    result, counts = method('base', ROSTER, rows, observe, cap, halve=halve)
    assert result.evaluations == len(paid) <= cap
    return (result.prompt, result.finalist, counts), paid


def necessary(incumbent, winner, grades, rows):
    """Independently price the shortest prefixes that prove the exact winner."""
    paid = {(incumbent, row) for row in rows}
    if winner is None:
        cutoff = sum(grades[incumbent, row] for row in rows)
    else:
        cutoff = sum(grades[winner, row] for row in rows)
    for candidate in ROSTER:
        upper = len(rows)
        loses_ties = winner is None or ROSTER.index(candidate) > ROSTER.index(winner)
        for row in rows:
            if candidate != winner and (upper < cutoff or (upper == cutoff and loses_ties)):
                break
            paid.add((candidate, row))
            upper -= not grades[candidate, row]
    return paid


def test_exhaustive_uniform_panels_preserve_results_with_minimal_paid_prefixes():
    keys = tuple(product(('base', *ROSTER), ROWS))
    for outcomes in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, outcomes, strict=True))
        for cap in (0, 4, 8, 12):
            before, original = run(quoted, grades, cap)
            after, used = run(screen, grades, cap)
            assert after == before
            rows = tuple(row for row, _ in _schedule(len(ROSTER), ROWS, cap, False))
            assert used == necessary('base', after[1], grades, rows)
            assert used <= original


def test_critical_panels_keep_the_original_validation():
    rows = (Row('critical', 'validation', critical=True), *ROWS[:2])
    grades = {(prompt, row): prompt == 'a' or (prompt == 'base' and row.critical)
              for prompt, row in product(('base', *ROSTER), rows)}
    assert run(screen, grades, 12, rows=rows) == run(quoted, grades, 12, rows=rows)
