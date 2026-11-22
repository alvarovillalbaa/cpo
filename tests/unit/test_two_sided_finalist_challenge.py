import pytest

from benchmarks.two_sided_finalist_challenge import FULL, MINIMUM, REPAIR, audit_headroom, previous, run_trial
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.single_finalist import FinalistResult


@pytest.mark.parametrize('policy', (FULL, MINIMUM))
def test_strict_replacement_reuses_the_entire_original_search_and_one_qualification(policy):
    cells = {'start': (0, 0, 0, 0, 0), 'first': (1, 0, 0, 1, 0), 'second': (1, 1, 1, 1, 1)}
    args = cells, 'start', ('first', 'second'), ((), (0, 1, 2), (3,), (4,)), 0, 13, 1
    base, before = previous.run_trial(previous.EXPECTED, args)
    result, after = run_trial(policy, args)

    assert base.prompt == 'first'
    assert result.prompt == 'second'
    old_search = [key for key in before if key[0] == 'validation']
    new_search = [key for key in after if key[0] == 'validation']
    assert len(old_search) < len(new_search) <= 13
    assert new_search[:len(old_search)] == old_search
    assert {(owner, case) for role, owner, case in after if role == 'qualification'} == {
        ('start', '3'), ('second', '3'),
    }


@pytest.mark.parametrize('policy', (FULL, MINIMUM))
def test_failed_challenge_keeps_the_original_qualification_observations(policy):
    cells = {'start': (0, 0, 0, 0), 'first': (1, 0, 0, 1), 'second': (1, 0, 0, 1)}
    args = cells, 'start', ('first', 'second'), ((), (0, 1, 2), (3,), ()), 0, 13, 1
    base, _ = previous.run_trial(previous.EXPECTED, args)
    result, _ = run_trial(policy, args)

    assert result.prompt == base.prompt == 'first'
    assert result.qualification == base.qualification
    assert result.search.evaluations > base.search.evaluations


def test_hindsight_distinguishes_a_strict_upgrade_from_an_unfundable_proof():
    cells = {'start': (0, 0, 0, 0, 0), 'first': (1, 0, 0, 1, 0), 'second': (1, 1, 1, 1, 1)}
    start, roster, roles = 'start', ('first', 'second'), ((), (0, 1, 2), (3,), (4,))
    baseline = FixedPoolCycleResult(FinalistResult('first', 'first', 5), None)
    paid = {('validation', 'first', '1'): False}

    assert audit_headroom(cells, start, roster, roles, baseline, paid, 1, 7) == 'betterStrictPromptExceedsMinimumReads'
    assert audit_headroom(cells, start, roster, roles, baseline, paid, 1, 8) == 'betterStrictPromptFitsInHindsight'


def test_repair_can_use_a_validation_tie_that_still_strictly_beats_the_incumbent():
    cells = {'start': (0, 0, 1, 0, 0), 'first': (1, 1, 0, 1, 0), 'second': (0, 1, 1, 1, 1)}
    args = cells, 'start', ('first', 'second'), ((), (0, 1, 2), (3,), (4,)), 0, 11, 1
    strict, _ = run_trial(MINIMUM, args)
    repaired, paid = run_trial(REPAIR, args)

    assert strict.prompt == 'first'
    assert repaired.prompt == 'second'
    assert paid['validation', 'first', '2'] is False
    assert paid['validation', 'second', '2'] is True
    assert ('qualification', 'first', '3') not in paid
