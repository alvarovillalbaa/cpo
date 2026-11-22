from itertools import product

from benchmarks.qualification_precheck_extension import cpo_trial, paired, precheck, reserve_cases
from cpo import Row


def test_reserved_cases_are_seeded_and_disjoint_from_every_original_role():
    original = (0, 1), (3, 4, 5), (6, 7, 8, 9), (10, 11, 12)
    expanded = reserve_cases(20, original, 'subject', 387)

    assert expanded == reserve_cases(20, original, 'subject', 387)
    assert expanded[:2] == original[:2] and expanded[3] == original[3]
    assert expanded[2][:4] == original[2]
    assert len(expanded[2]) == 6
    assert not set(expanded[2][4:]) & set().union(*original)


def test_precheck_has_exact_activation_and_search_bounds_for_every_incumbent_profile():
    rows = tuple(Row(str(i), 'qualification') for i in range(6))
    for bits, gain in product(product((False, True), repeat=6), (1, 2)):
        paid = []

        def read(prompt, row, repeat):
            assert prompt == 'start' and repeat == 0
            paid.append(row.id)
            return bits[int(row.id)]

        active, history, misses, upper = precheck('start', rows[:4], rows[4:], gain, read)
        width = 6 if bits[:4].count(False) < gain else 4
        assert active == rows[:width]
        assert paid == [row.id for row in active[:len(history)]]
        assert upper == width - len(history) + misses
        assert (upper >= gain) == (bits[:width].count(False) >= gain)


def test_extension_recovers_a_gain_and_credits_the_paid_incumbent_prefix():
    cells = {'start': (0, 0, 0, 1, 1, 1, 1, 0, 0), 'rival': (1, 1, 1, 1, 1, 1, 1, 1, 1)}
    roles = (), (0, 1, 2), (3, 4, 5, 6, 7, 8), ()
    result, paid = paired.cycle.execute_path(cpo_trial, cells, 'start', ('rival',), roles, 1, 7, 1)

    assert result.prompt == 'rival'
    assert list(paid)[:5] == [('qualification', 'start', str(i)) for i in range(3, 8)]
    assert result.qualification_evaluations <= 12
    assert result.search.evaluations <= 7


def test_six_incumbent_passes_close_the_precheck_without_search():
    cells = {'start': (0, 0, 0, 1, 1, 1, 1, 1, 1), 'rival': (1, 1, 1, 1, 1, 1, 1, 1, 1)}
    roles = (), (0, 1, 2), (3, 4, 5, 6, 7, 8), ()
    result, paid = paired.cycle.execute_path(cpo_trial, cells, 'start', ('rival',), roles, 1, 7, 1)

    assert result.prompt == 'start'
    assert result.search.evaluations == 0
    assert list(paid) == [('qualification', 'start', str(i)) for i in range(3, 9)]
