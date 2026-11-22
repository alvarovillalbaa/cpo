from contextlib import nullcontext

import pytest

from benchmarks.shared_validation_split_safe_transfer import native, split_loaders, split_safe_cache, validation_width


def test_loader_ids_preserve_the_order_in_each_disjoint_split():
    training = ({'case': 9}, {'case': 1})
    validation = ({'case': 7}, {'case': 3})
    left, right = split_loaders(training, validation)

    assert left.all_ids() == [0, 1]
    assert right.all_ids() == [2, 3]
    assert [row['case'] for row in left.fetch(left.all_ids())] == [9, 1]
    assert [row['case'] for row in right.fetch(right.all_ids())] == [7, 3]
    with pytest.raises(ValueError, match='disjoint'):
        split_loaders(training, (*validation, training[0]))


def test_shortening_native_validation_preserves_every_other_argument():
    roles = (0, 1), (2, 3, 4, 5, 6, 7), (8, 9), (10, 11)
    args = {}, 'start', ('rival',), roles, 53
    shortened = validation_width(args, 3)

    assert shortened[:3] == args[:3]
    assert shortened[3] == (roles[0], roles[1][:3], roles[2], roles[3])
    assert shortened[4] == args[4]


@pytest.mark.parametrize('batched', (False, True))
def test_split_safe_native_search_pays_for_validation_and_retains_the_true_winner(batched):
    def run(context):
        paid = {}

        def grade(prompt, case):
            passed = (prompt == 'start' and case == 6) or (prompt != 'start' and case < 6)
            paid[prompt, case] = passed
            return passed

        with context():
            chosen, _ = native.native_cost.adapter.math.gepa.optimize_by_paid_reads(
                'start', ('rival', 'other'), tuple(range(6)), tuple(range(6, 12)), grade,
                lambda: len(paid), paid_limit=42, batched=batched, seed=17,
            )
        return chosen, paid

    historical, old = run(nullcontext)
    corrected, paid = run(split_safe_cache)
    assert historical in ('rival', 'other')
    assert corrected == 'start'
    assert sum(prompt == historical and case >= 6 for prompt, case in old) < 6
    assert sum(prompt == historical and case >= 6 for prompt, case in paid) == 6
