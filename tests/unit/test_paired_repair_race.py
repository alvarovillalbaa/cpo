from itertools import product

import pytest

from benchmarks.paired_repair_race import paired_repair_screen
from cpo import Observation, Row


def evaluate_screen(rows, roster, correct, cap, miss_limit):
    paid = {}

    def evaluate(prompt, row):
        key = prompt, row.id
        assert key not in paid
        paid[key] = correct[key]
        return Observation(paid[key], {})

    outcome, counts = paired_repair_screen('base', roster, rows, evaluate, cap, miss_limit=miss_limit)
    assert outcome.evaluations == len(paid) <= cap
    return outcome, counts, paid


@pytest.mark.parametrize('cap,limit,finalist', [(10, 1, None), (10, 2, 'rival'), (5, 2, None)])
def test_two_repairs_compensate_for_one_regression_only_when_funded(cap, limit, finalist):
    rows = tuple(Row(i, 'validation') for i in ('miss-one', 'pass', 'miss-two'))
    grades = {('base', row.id): row.id == 'pass' for row in rows}
    grades.update({('rival', row.id): row.id != 'pass' for row in rows})
    outcome, counts, paid = evaluate_screen(rows, ('rival',), grades, cap, limit)
    assert outcome.finalist == finalist
    assert counts == (((1, 3), (2, 3)) if finalist else None)
    assert (('rival', 'miss-two') in paid) == (finalist is not None)


def test_preservation_reads_are_reserved_for_paid_repairs():
    rows = tuple(Row(i, 'validation') for i in ('pass', 'miss'))
    grades = {('base', 'pass'): True, ('base', 'miss'): False,
              ('untested', 'miss'): False, ('winner', 'miss'): True, ('winner', 'pass'): True}
    outcome, counts, paid = evaluate_screen(rows, ('untested', 'winner'), grades, 10, 1)
    assert outcome.finalist == 'winner'
    assert ('untested', 'pass') not in paid
    assert counts == ((1, 2), (2, 2))


def test_every_small_panel_nomination_has_an_exact_paired_gain_within_cap():
    rows = tuple(Row(str(i), 'validation') for i in range(3))
    roster = 'a', 'b'
    keys = tuple(product(('base', *roster), (row.id for row in rows)))
    for values in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, values))
        for cap, limit in product(range(3, 10), (1, 2)):
            result, counts, paid = evaluate_screen(rows, roster, grades, cap, limit)
            if result.finalist is None:
                assert counts is None
                continue
            common = [row.id for row in rows if ('base', row.id) in paid and (result.finalist, row.id) in paid]
            old = sum(paid['base', case] for case in common)
            new = sum(paid[result.finalist, case] for case in common)
            assert counts == ((old, len(common)), (new, len(common))) and new > old
