from itertools import product

from benchmarks.recorded_promotion_coverage import assign_panels


def test_assignment_keeps_panel_sizes_and_reserves_a_critical_validation_case_when_possible():
    ids = tuple('abcdef')
    validation, promotion = ids[:3], ids[3:]
    for tags in product((False, True), repeat=len(ids)):
        metadata = {case: {'critical': value} for case, value in zip(ids, tags)}
        critical = {case for case, value in zip(ids, tags) if value}
        for target in (1, 2):
            new_validation, new_promotion = assign_panels(validation, promotion, metadata, target)
            possible = len(critical) - int(len(critical) >= 2)
            assert len(new_validation) == len(new_promotion) == 3
            assert set(new_validation).isdisjoint(new_promotion) and set(new_validation + new_promotion) == set(ids)
            assert len(critical.intersection(new_promotion)) >= min(target, possible)
            if len(critical) >= 2:
                assert critical.intersection(new_validation)
            changed = len(set(new_promotion) - set(promotion))
            assert changed == abs(len(critical.intersection(new_promotion)) - len(critical.intersection(promotion)))


def test_unchanged_policy_keeps_case_order_for_both_roles():
    assert assign_panels(('z', 'x'), ('y', 'a'), {}, 0) == (['z', 'x'], ['y', 'a'])
