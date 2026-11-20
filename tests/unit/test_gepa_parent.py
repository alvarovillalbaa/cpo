"""Verify exact two-candidate draws and random state against native GEPA."""

from itertools import product
from random import Random

from gepa.gepa_utils import select_program_candidate_from_pareto_front

from cpo.gepa_parent import select_two_candidate_parent
from cpo.sequential_field_rewrite import SequentialValidationGrades


def native_parent(profiles, rng):
    fronts = {case: {owner for owner, score in enumerate(pair) if score == max(pair)}
              for case, pair in enumerate(zip(*profiles, strict=True))}
    averages = [sum(row) / len(row) for row in profiles]
    return select_program_candidate_from_pareto_front(fronts, averages, rng)


def test_partial_draw_matches_native_on_every_small_field_profile_and_seed():
    pool = ('old', 'new')
    saved = 0
    for values in product((0.0, 0.5, 1.0), repeat=6):
        profiles = (values[:3], values[3:])
        for seed in range(8):
            before, partial = Random(seed), Random(seed)
            paid = {}

            def read(prompt, index):
                assert (prompt, index) not in paid
                value = profiles[pool.index(prompt)][index]
                paid[prompt, index] = value
                return value

            def forbid_profile(_prompt):
                raise AssertionError('Read a complete profile')

            grades = SequentialValidationGrades(
                forbid_profile, lambda prompt, index: paid.get((prompt, index)), read,
            )
            parent = select_two_candidate_parent(pool, 3, grades, partial)
            assert parent == pool[native_parent(profiles, before)]
            assert before.getstate() == partial.getstate()
            saved += 6 - len(paid)
    assert saved > 0


def test_prepaid_perfect_rows_do_not_buy_redundant_older_grades():
    pool = ('old', 'new')
    profiles = ((0.0,) * 12, (0.5,) + (1.0,) * 11)
    paid = {('new', case): 1.0 for case in range(1, 12)}

    def read(prompt, case):
        paid[prompt, case] = profiles[pool.index(prompt)][case]
        return paid[prompt, case]

    grades = SequentialValidationGrades(lambda _: (), lambda prompt, case: paid.get((prompt, case)), read)
    before, partial = Random(0), Random(0)
    assert select_two_candidate_parent(pool, 12, grades, partial) == pool[native_parent(profiles, before)]
    assert before.getstate() == partial.getstate()
    assert len(paid) < 24


def test_distinct_two_candidate_scope_leaves_larger_draws_to_the_complete_scheduler():
    rng = Random(42)
    state = rng.getstate()
    for pool, size in ((('one', 'two', 'three'), 12), (('one', 'two'), 33), (('one', 'one'), 12)):
        assert select_two_candidate_parent(pool, size, None, rng) is None
        assert rng.getstate() == state
