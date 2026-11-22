from itertools import product

from benchmarks.incumbent_first_paid_repair import incumbent_first_screen
from benchmarks.paid_validation_agreement import guarded_screen
from cpo import Observation, Row


def measure(screen, incumbent, candidates, rows, grades, cap, **settings):
    paid = []

    def evaluate(prompt, row):
        key = prompt, row
        assert key not in paid
        paid.append(key)
        return Observation(grades[key], {})

    result, proof = screen(incumbent, candidates, rows, evaluate, cap, **settings)
    assert len(paid) == result.evaluations <= cap
    return (result.prompt, result.finalist, proof), paid


def test_admission_and_priors_match_for_every_small_matrix_and_cap():
    rows = tuple(Row(str(i), 'validation') for i in range(3))
    incumbent, candidates = 'base', ('first', 'second', 'third')
    keys = tuple(product((incumbent, *candidates), rows))
    for replies in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, replies))
        for cap in range(len(rows), 13):
            old, before = measure(guarded_screen, incumbent, candidates, rows, grades, cap, seek=False)
            actual, after = measure(incumbent_first_screen, incumbent, candidates, rows, grades, cap)
            assert actual == old
            assert all(prompt == incumbent for prompt, _ in set(after) - set(before))


def test_perfect_incumbent_skips_every_challenger_and_ignores_unscheduled_cases():
    rows = tuple(Row(str(i), 'validation') for i in range(6))
    grade = {('base', row): True for row in rows[:3]}
    (prompt, finalist, evidence), paid = measure(incumbent_first_screen, 'base', ('challenger',), rows, grade, 19)
    assert (prompt, finalist, evidence) == ('base', None, None)
    assert paid == [('base', row) for row in rows[:3]]


def test_prepaid_miss_is_charged_even_when_every_challenger_is_already_eliminated():
    rows = tuple(Row(str(i), 'validation') for i in range(3))
    grades = {('base', rows[0]): True, ('base', rows[1]): True, ('base', rows[2]): False,
              ('challenger', rows[0]): False, ('challenger', rows[1]): False}
    baseline, before = measure(guarded_screen, 'base', ('challenger',), rows, grades, 6, seek=False)
    actual, after = measure(incumbent_first_screen, 'base', ('challenger',), rows, grades, 6)
    assert actual == baseline == ('base', None, None)
    assert set(after) - set(before) == {('base', rows[2])}


def test_critical_case_preserves_original_callback_order():
    rows = Row('ordinary', 'validation'), Row('protected', 'validation', critical=True)
    grades = {(prompt, row): row.critical or prompt == 'challenger'
              for prompt, row in product(('base', 'challenger'), rows)}
    assert measure(incumbent_first_screen, 'base', ('challenger',), rows, grades, 19) == (
        measure(guarded_screen, 'base', ('challenger',), rows, grades, 19, seek=False)
    )
