"""T2 scripted evidence for shared-budget task queues."""

from fractions import Fraction

from benchmarks.continuous_archive_backup import Episode, Opportunity
from benchmarks.continuous_backup_allocation import DISCOUNT, EQUAL, GLOBAL, PROPORTIONAL, allocation_key, rollout
from cpo.optimizer import Row
from cpo.paired_qualification import QualificationObservation


def test_charge_equalization_changes_task_order_and_keeps_full_start_quote():
    episodes, options = [], {}
    for index, subject in enumerate(('a', 'a', 'b')):
        episodes.append(Episode(subject, index, 'base', 'base', 'failed', ('backup',),
                                (Row('0', 'qualification'),), (), {'base': (False,), 'backup': (True,)},
                                {('qualification', 'base', '0'): False},
                                (QualificationObservation('base', '0', 0, False),), 1))
        options[index] = [Opportunity('backup', None, ((0, 1), (1, 1)), 2, Fraction(9 - index, 10))]
    priors = {None: (1, 1, 1, 1)}
    global_path, global_receipt = rollout(GLOBAL, episodes, options, 3, priors)
    equal_path, equal_receipt = rollout(EQUAL, episodes, options, 3, priors)
    assert tuple(global_path) == (0, 1)
    assert tuple(equal_path) == (0, 2)
    assert dict(global_receipt['lookupsByTask']) == {'a': 2}
    assert dict(equal_receipt['lookupsByTask']) == {'a': 1, 'b': 1}
    assert global_receipt['unspent'] == equal_receipt['unspent'] == 1


def test_proportional_and_discounted_modes_use_paid_spend_per_task():
    head = (-Fraction(3, 4), 0, 0)
    assert allocation_key(PROPORTIONAL, head, 4, 20, 20, 100)[0] == Fraction(1, 5)
    assert allocation_key(PROPORTIONAL, head, 4, 40, 20, 100)[0] == Fraction(1, 10)
    assert allocation_key(DISCOUNT, head, 4, 20, 20, 100)[0] == -Fraction(3, 8)
    assert allocation_key(DISCOUNT, head, 0, 20, 20, 100) == head
