"""Verify the cost bounds against enumeration and the published replay costs."""

from fractions import Fraction
from itertools import product
import json

from benchmarks.certified_opening_cost_sensitivity import DATA, describe, extreme_ratio, measure


def test_fractional_extrema_match_every_endpoint_assignment():
    for counts in product(range(3), repeat=6):
        terms = [(counts[2 * i], counts[2 * i + 1], 2 + i, 3 + i, 7 + i) for i in range(3)]
        fixed = (16, 20)
        enumerated = []
        for prices in product(*(row[2:5:2] for row in terms)):
            totals = [fixed[arm] + sum(row[arm] * price for row, price in zip(terms, prices, strict=True))
                      for arm in range(2)]
            enumerated.append(Fraction(*totals))
        assert extreme_ratio(terms, fixed, maximize=False) == min(enumerated)
        assert extreme_ratio(terms, fixed, maximize=True) == max(enumerated)
        observed = describe(terms, fixed)
        minimum, maximum = map(Fraction, observed['sharedChargeSavingsFraction'])
        separate_lower, separate_upper = map(Fraction, observed['separateChargeSavingsFraction'])
        assert separate_lower <= minimum <= maximum <= separate_upper


def test_bundle_reproduces_the_observed_costs_and_ten_percent_gate():
    result = measure(json.loads(DATA.read_bytes()))
    assert result['pooled']['originalCostMicrousd'] == {'cpo': 20_842_344, 'gepa': 23_456_712}
    assert result['pooled']['sharedChargesAlwaysSaveAtLeastTenPercent']
    assert not result['pooled']['separateChargesAlwaysSaveAtLeastTenPercent']
    assert all(row['sharedChargesAlwaysSaveAtLeastTenPercent'] for row in result['byPhase'].values())
    assert not result['byTask']['outage']['sharedChargesAlwaysSaveAtLeastTenPercent']
    assert result['pooled']['pairedScores'] == {
        'cpoPasses': 382, 'gepaPasses': 382, 'matchedUses': 480, 'distinctCases': 36,
        'differentSelectedPrompts': 0, 'pairedGains': 0, 'pairedLosses': 0, 'casesWithLowerTotal': 0,
    }
