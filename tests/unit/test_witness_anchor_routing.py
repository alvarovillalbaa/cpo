from random import Random

import pytest

from benchmarks import witness_anchor_routing as replay


def subject(passes, cost, ceiling):
    return {'cases': {replay.FULL: [0, 0], replay.BOUNDS: passes},
            'costs': {replay.FULL: 8, replay.BOUNDS: cost, replay.retry.BASE: ceiling},
            'wideEpisodes': {replay.FULL: 0, replay.BOUNDS: 1}, 'decisionsPerCase': 1}


def test_fit_chooses_highest_macro_score_within_seeded_training_cost():
    menu = (replay.FULL, replay.BOUNDS)

    assert replay.fit([subject([1, 1], 11, 10)], menu) == replay.FULL
    assert replay.fit([subject([1, 1], 10, 10)], menu) == replay.BOUNDS
    assert replay.fit([subject([0, 0], 10, 10)], menu) == replay.FULL


def test_held_out_subject_is_excluded_from_training_gain_and_cost():
    menu = (replay.FULL, replay.BOUNDS)
    groups = {'test': subject([1, 1], 8, 20), 'train': subject([1, 1], 11, 10)}

    assert replay.fit(list(groups.values()), menu) == replay.BOUNDS
    assert replay.held_out(groups, 'test', menu) == replay.FULL


def test_opening_requires_two_identical_paid_grades():
    layout = {'validation': [1, 2, 3, 4], 'seed': 8}
    order = layout['validation'].copy()
    Random(layout['seed']).shuffle(order)
    a, b = [('start', case) for case in order[:2]]
    paid = {a: True, b: False}

    assert replay.opening('start', layout, paid, paid.copy()) == 1
    with pytest.raises(ValueError, match='same two opening grades'):
        replay.opening('start', layout, paid, {a: True})
    with pytest.raises(ValueError, match='same two opening grades'):
        replay.opening('start', layout, paid, {a: True, b: True})


def test_fractional_route_requires_both_opening_and_hash_eligibility():
    assert replay.open_route(1, 4, 0, 3) == replay.BOUNDS
    assert replay.open_route(1, 4, 0, 4) == replay.FULL
    assert replay.open_route(1, 4, 1, 0) == replay.FULL
