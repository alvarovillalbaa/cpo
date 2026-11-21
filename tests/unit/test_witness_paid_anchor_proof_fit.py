from collections import Counter

import pytest

from benchmarks import witness_paid_anchor_proof_fit as replay


def test_proof_rules_use_pessimistic_anchor_bounds_and_already_paired_grades():
    layout = {'validation': [0, 1, 2, 3], 'seed': 8}
    grades = {('start', 0): False, ('start', 1): False, ('start', 2): True,
              ('new', 0): True, ('new', 1): True, ('new', 2): True}

    assert replay.eligible_rules('start', 'new', layout, grades, 1) == {
        'all', 'preserve-paid-passes', 'two-net-paired-wins', 'half', 'three-quarters'}
    grades['new', 3] = True
    grades['start', 4], grades['new', 4] = True, False
    assert replay.eligible_rules('start', 'new', layout, grades, 3) == {'all', 'two-anchor-wins'}
    del grades['new', 3], grades['new', 0]
    with pytest.raises(ValueError, match='strict anchor gain'):
        replay.eligible_rules('start', 'new', layout, grades, 0)


def test_skipping_a_proof_restores_the_incumbent_and_refunds_only_proof_lookups():
    arm = replay.parent.PROVED
    group = {'cases': {method: [3, 2] for method in replay.CAPS},
             'costs': dict.fromkeys(replay.CAPS, 20)}
    events = {('subject', 16): [(('subject', 'model', 1), {'all'}, 5, (1, -1))]}

    replay.materialize({'subject': group}, events)

    assert group['cases'][arm, 'no-proof'] == [2, 3]
    assert group['costs'][arm, 'no-proof'] == 15
    assert group['extraProofs'][arm, 'no-proof'] == 0
    assert group['cases'][arm, 'all'] == [3, 2]
    assert group['costs'][arm, 'all'] == 20
    assert group['extraProofs'][arm, 'all'] == 1


def test_fit_excludes_every_outcome_and_cost_of_the_evaluated_subject():
    menu = replay.MENUS[replay.PRIMARY]
    winner = replay.parent.PROVED, 'preserve-paid-passes'
    choices = {arm: [0] for arm in menu}
    choices[winner] = [1]
    costs = dict.fromkeys(menu, 10)
    costs[replay.replay.retry.BASE] = 10
    group = {'cases': choices, 'costs': costs, 'decisionsPerCase': 1, 'wideEpisodes': Counter()}
    family = {'train': group, 'test': {}}

    assert replay.fit_subject(family, 'test', replay.PRIMARY) == winner
