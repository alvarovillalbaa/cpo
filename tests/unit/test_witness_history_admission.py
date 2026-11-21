from fractions import Fraction

import pytest

from benchmarks import witness_history_admission as history


def test_history_ranking_excludes_all_current_roles_and_unenrolled_candidates():
    layouts = [{'train': [1], 'validation': [2], 'qualify': [3]}]
    excluded = history.excluded_cases([4], layouts)
    ledger = {'old': dict.fromkeys(range(1, 10), False), 'overlap': dict.fromkeys(range(1, 5), True),
              'paid-rival': {5: True, 6: True, 7: False}, 'unpaid': dict.fromkeys(range(5, 10), True)}

    winner, support, scores = history.rank('old', ('overlap', 'paid-rival'), ledger, excluded)

    assert excluded == {1, 2, 3, 4}
    assert winner == 'paid-rival'
    assert support == {'overlap': 0, 'paid-rival': 3}
    assert scores == {'paid-rival': Fraction(2, 5)}


def test_one_prior_win_does_not_meet_the_matched_history_floor():
    ledger = {'old': {1: False}, 'rival': {1: True}}

    assert history.rank('old', ['rival'], ledger, set()) == (None, {'rival': 1}, {})


def test_paid_pairs_are_deduplicated_and_conflicting_history_is_rejected():
    ledger = {}
    history.add_paid(ledger, {('rival', 1): True})
    history.add_paid(ledger, {('rival', 1): True})

    assert ledger == {'rival': {1: True}}
    with pytest.raises(ValueError, match='previously evaluated pair'):
        history.add_paid(ledger, {('rival', 1): False})
