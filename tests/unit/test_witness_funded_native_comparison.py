import pytest

from benchmarks import witness_funded_native_comparison as comparison


def fixture():
    start = comparison.native.replay.START
    choices = (start, 'small', 'large', comparison.SINGLE, comparison.FUNDED)
    groups = {name: {'caseIds': [0], 'decisionsPerCase': 1,
                     'cases': dict(zip(choices, ([0], [int(name == 'a')], [1], [1], [1]), strict=True)),
                     'paidLookups': dict(zip(choices, costs, strict=True))}
              for name, costs in (('a', (0, 1, 8, 1, 2)), ('b', (0, 1, 4, 3, 5)))}
    passes = {arm: sum(row['cases'][arm][0] for row in groups.values()) for arm in choices}
    totals = {arm: {'holdoutPasses': passes[arm], 'macroAccuracy': ('0', '1/2', '1')[passes[arm]],
                    'paidLookups': sum(row['paidLookups'][arm] for row in groups.values())}
              for arm in choices}
    return groups, ('small', 'large'), {'draws': 32, 'seed': 33}, totals


def test_reselection_uses_the_spend_of_each_policy_on_the_drawn_subjects():
    groups, settings, plan, totals = fixture()

    report = comparison.compare(groups, settings, plan, totals, {'totals': totals}, 8)

    funded = report['comparisons'][comparison.FUNDED]
    single = report['comparisons'][comparison.SINGLE]
    assert funded['observedBestAffordableNative'] == 'small'
    assert funded['selectedNativeDraws']['large'] > 0
    assert single['selectedNativeDraws'].get('large', 0) == 0
    assert not report['qualifies']


def test_mismatched_native_totals_block_the_paired_claim():
    groups, settings, plan, totals = fixture()
    totals['large']['paidLookups'] -= 1

    with pytest.raises(ValueError, match='frozen native total'):
        comparison.compare(groups, settings, plan, totals, {'totals': totals}, 8)
