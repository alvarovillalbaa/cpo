from collections import Counter
from fractions import Fraction
from itertools import product

from benchmarks import recorded_adaptive_certificate_race as study
from cpo import Observation, Row


def test_modeled_cost_and_probability_include_early_rejection_and_critical_guards():
    assert study.prospects(((False, 2), (False, 2)), 1) == (Fraction(3, 4), Fraction(3, 2))
    assert study.prospects(((True, 2), (False, 2)), 1) == (Fraction(1, 2), 1)
    assert study.prospects(((True, 2),), 0) == (Fraction(1, 2), 1)
    assert study.prospects(((False, 2),), 2) == (0, 0)


def test_every_small_paid_race_finds_a_certificate_exactly_when_one_is_available():
    prompts = ('start', 'first', 'second')
    rows = (Row('v1', 'validation', critical=True), Row('v2', 'validation'), Row('v3', 'validation'))
    training = (Row('t1', 'training'),)
    keys = tuple((prompt, row.id) for prompt in prompts for row in rows)
    switched = False
    for grades in product((False, True), repeat=len(keys)):
        board = dict(zip(keys, grades, strict=True))
        target = sum(grades[:3]) + 1
        valid = {prompt for prompt in prompts[1:] if sum(board[prompt, row.id] for row in rows) >= target
                 and (not grades[0] or board[prompt, rows[0].id])}
        ledger, audit = {}, Counter()

        def read(prompt, row):
            key = prompt, row.id
            assert key not in ledger
            ledger[key] = Observation(board[key], {})
            return board[key], 1

        result = study.race(prompts[0], prompts[1:], rows, training, read, ledger, cap=11, audit=audit)
        assert (result is None) == (not valid)
        if result:
            winner, reads = result
            assert winner in valid
            assert sum(ledger[winner, row.id].passed for row in rows if (winner, row.id) in ledger) >= target
            assert reads == sum(prompt == winner for prompt, _ in ledger)
            assert len(ledger) + 2 * len(training) <= 11
        assert len(ledger) == len(rows) + audit['challengerReads']
        switched |= audit['challengerSwitches'] > 0
    assert switched


def test_race_does_not_buy_a_probe_without_the_original_full_training_reserve():
    rows, training = (Row('v', 'validation'),), (Row('t', 'training'),)
    ledger, audit = {}, Counter()

    def read(prompt, row):
        assert prompt == 'start'
        ledger[prompt, row.id] = Observation(False, {})
        return False, 1

    assert study.race('start', ('new',), rows, training, read, ledger, cap=3, audit=audit) is None
    assert list(ledger) == [('start', 'v')]
