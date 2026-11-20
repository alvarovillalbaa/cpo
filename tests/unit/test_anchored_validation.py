"""T2 exact outcome fixtures for validation with an already measured anchor."""

from collections import Counter
from itertools import product

from cpo import Row
from cpo.anchored_validation import certify_validation_gain


def test_all_five_row_outcomes_match_full_validation_with_and_without_a_cache():
    rows = [Row('a0', 'a', critical=True), Row('b0', 'b'), Row('a1', 'a'),
            Row('b1', 'b', critical=True), Row('b2', 'b')]
    cases = [row.id for row in rows]
    for outcomes in product((False, True), repeat=2 * len(rows)):
        before = dict(zip(cases, outcomes[:len(rows)], strict=True))
        after = dict(zip(cases, outcomes[len(rows):], strict=True))
        gains = Counter()
        for row in rows:
            gains[row.family] += after[row.id] - before[row.id]
        expected = (gains.total() > 0 and min(gains.values()) >= 0
                    and all(not row.critical or not before[row.id] or after[row.id] for row in rows))
        for known in ({}, {'a0': after['a0'], 'b1': after['b1']}, after):
            observed = []

            def evaluate(row):
                assert row.id not in known and row.id not in observed
                observed.append(row.id)
                return after[row.id]

            assert certify_validation_gain(rows, before, evaluate, known=known) == expected


def test_critical_loss_stops_before_reading_ordinary_rows():
    rows = [Row('ordinary', 'a'), Row('critical', 'a', critical=True)]
    observed = []

    def evaluate(row):
        observed.append(row.id)
        return False

    assert not certify_validation_gain(rows, {'ordinary': False, 'critical': True}, evaluate)
    assert observed == ['critical']
