from itertools import product
from random import Random

from gepa.gepa_utils import select_program_candidate_from_pareto_front

from cpo.gepa_frontier import _certify, select_frontier_parent
from cpo.sequential_field_rewrite import SequentialValidationGrades


def native_draw(profiles, rng):
    fronts = {case: {i for i, score in enumerate(row) if score == max(row)}
              for case, row in enumerate(zip(*profiles, strict=True))}
    return select_program_candidate_from_pareto_front(fronts, [sum(p) / len(p) for p in profiles], rng)


def check_draw(profiles, seed, prepaid, *, prioritize_uncertain_cases=False, adaptive_case_order=False):
    width, size = len(profiles), len(profiles[0])
    pool = tuple(f'prompt-{i}' for i in range(width))
    paid = {(pool[i], case): profiles[i][case] for i, case in prepaid}
    expected_rng, actual_rng = Random(seed), Random(seed)

    def read(prompt, case):
        assert (prompt, case) not in paid
        paid[prompt, case] = profiles[pool.index(prompt)][case]
        return paid[prompt, case]

    def complete(prompt):
        return tuple(paid[prompt, case] if (prompt, case) in paid else read(prompt, case) for case in range(size))

    grades = SequentialValidationGrades(complete, lambda prompt, case: paid.get((prompt, case)), read)
    parent = select_frontier_parent(pool, size, grades, actual_rng,
                                    prioritize_uncertain_cases=prioritize_uncertain_cases,
                                    adaptive_case_order=adaptive_case_order)
    if parent is None:
        assert actual_rng.getstate() == expected_rng.getstate()
        parent = pool[native_draw(tuple(grades(prompt) for prompt in pool), actual_rng)]
    assert parent == pool[native_draw(profiles, expected_rng)]
    assert actual_rng.getstate() == expected_rng.getstate()
    return width * size - len(paid)


def test_every_small_three_candidate_profile_and_mixed_partial_cache():
    saved = 0
    cells = tuple(product(range(3), range(2)))
    for values in product((0.0, 0.5, 1.0), repeat=6):
        profiles = (values[:2], values[2:4], values[4:])
        for seed in range(4):
            rng = Random(f'{values!r}/{seed}')
            prepaid = tuple(cell for cell in cells if rng.randrange(2))
            saved += check_draw(profiles, seed, prepaid)
            check_draw(profiles, seed, prepaid, adaptive_case_order=True)
    assert saved > 0


def test_mixed_fronts_and_later_pools_match_native():
    for seed in range(64):
        rng = Random(seed)
        width = 3 + seed % 5
        size = 1 + seed % 12
        profiles = tuple(tuple(rng.choice((0.0, 0.25, 0.5, 0.75, 1.0)) for _ in range(size))
                         for _ in range(width))
        prepaid = tuple((i, case) for i in range(width) for case in range(size) if rng.randrange(3))
        check_draw(profiles, seed, prepaid)
        check_draw(profiles, seed, prepaid, prioritize_uncertain_cases=True)
        check_draw(profiles, seed, prepaid, adaptive_case_order=True)


def test_draw_can_ignore_uncertain_owner_of_the_other_case():
    profiles = ((1.0, 0.25), (0.5, 0.75), (0.25, 1.0))
    prepaid = tuple(cell for cell in product(range(3), range(2)) if cell != (2, 1))
    assert check_draw(profiles, 1, prepaid) == 1
    assert check_draw(profiles, 0, prepaid) == 0


def test_ambiguous_removal_order_and_unsupported_scope_do_not_advance_rng():
    rng = Random(7)
    before = rng.getstate()
    # Either the middle candidate owns both cases, or both outer ones survive.
    assert _certify(((0b011,), (0b110,)), 3, rng) is None
    assert select_frontier_parent(('a', 'a', 'b'), 4, None, rng) is None
    assert select_frontier_parent(('a', 'b', 'c'), 33, None, rng) is None
    assert rng.getstate() == before
