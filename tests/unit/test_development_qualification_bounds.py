from itertools import product

import pytest

from cpo.development_qualification import Sample, rejection_reasons
from cpo.development_qualification_bounds import assess_development_bounds


GATE = {'minimumPassesPerTask': 1, 'minimumAddedPasses': 1, 'maxSearchCostPercentForEfficiency': 90}


def test_matches_every_completion_of_a_panel_with_caps_and_shared_replies():
    schedule = (
        Sample('task', 'critical', 0, True, ('cpo', 'initial')),
        Sample('task', 'critical', 0, True, ('gepa',)),
        Sample('task', 'critical', 1, True, ('cpo',)),
        Sample('task', 'critical', 1, True, ('initial', 'gepa')),
        Sample('task', 'ordinary', 0, False, ('cpo', 'gepa')),
        Sample('task', 'ordinary', 0, False, ('initial',)),
    )
    for floor, cost in product((1, 2), (80, 95)):
        gate = {**GATE, 'minimumPassesPerTask': floor}
        costs = {'cpo': cost, 'gepa': 100}
        for observed in product((None, False, True), repeat=len(schedule)):
            known = sum(value is None for value in observed)
            decisions = set()
            for assignment in product((False, True), repeat=known):
                missing = iter(assignment)
                complete = tuple(next(missing) if grade is None else grade for grade in observed)
                decisions.add(not rejection_reasons(schedule, complete, gate, costs))
            expected = {frozenset({True}): 'guaranteed', frozenset({False}): 'impossible',
                        frozenset({False, True}): 'undetermined'}[frozenset(decisions)]
            assert assess_development_bounds(schedule, observed, gate=gate, search_costs=costs).status == expected


def test_unknown_shared_reply_cannot_supply_an_unmatched_gain():
    schedule = (Sample('task', 'critical', 0, True, ('cpo', 'initial', 'gepa')),)
    costs = {'cpo': 100, 'gepa': 100}
    verdict = assess_development_bounds(schedule, (None,), gate=GATE, search_costs=costs)
    assert verdict.status == 'impossible'
    assert verdict.rejection_reasons == ({'gate': 'quality-or-efficiency', 'arm': 'gepa', 'maximumAddedPasses': 0},)
    assert assess_development_bounds(schedule, (), gate=GATE, search_costs=costs) == verdict


@pytest.mark.parametrize('observations', [(1,), (True, None)])
def test_rejects_invalid_observations(observations):
    schedule = (Sample('task', 'critical', 0, True, ('cpo', 'initial', 'gepa')),)
    with pytest.raises(ValueError, match='one boolean or None'):
        assess_development_bounds(schedule, observations, gate=GATE, search_costs={'cpo': 90, 'gepa': 100})
