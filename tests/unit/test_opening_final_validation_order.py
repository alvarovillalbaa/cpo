from itertools import product

import pytest

from benchmarks.opening_final_validation_order import tight_family_certificate
from cpo import Row
from cpo.anchored_validation import certify_validation_gain
from cpo.family_ordered_validation import certify_family_ordered_validation_gain


def test_tight_family_first_can_find_an_irreversible_regression_sooner():
    rows = [Row('loose', 'A'), Row('tight', 'B')]
    anchor = {'loose': False, 'tight': True}
    replies = {'loose': True, 'tight': False}
    traces = [[], []]
    for algorithm, trace in zip((certify_validation_gain, tight_family_certificate), traces, strict=True):
        def observe(row):
            trace.append(row.id)
            return replies[row.id]

        assert not algorithm(rows, anchor, observe)
    assert traces == [['loose', 'tight'], ['tight']]


def test_original_order_when_every_unread_reply_must_pass():
    rows = [Row('loose', 'A'), Row('tight', 'B')]
    reads = []

    def fail(row):
        reads.append(row.id)
        return False

    assert not certify_family_ordered_validation_gain(rows, {'loose': False, 'tight': True}, fail)
    assert reads == ['loose']


@pytest.mark.parametrize('algorithm', (tight_family_certificate, certify_family_ordered_validation_gain))
def test_tight_family_order_preserves_exact_decisions_with_partial_replies(algorithm):
    rows = [Row('a', 'A', True), Row('b', 'A'), Row('c', 'B', True), Row('d', 'B')]
    ids = [row.id for row in rows]
    outcomes = list(product((False, True), repeat=len(rows)))
    for initial, candidate, cached in product(outcomes, repeat=3):
        anchor, current = (dict(zip(ids, values, strict=True)) for values in (initial, candidate))
        known = {key: current[key] for key, available in zip(ids, cached, strict=True) if available}
        visits = set()

        def observe(row):
            assert row.id not in known and row.id not in visits
            visits.add(row.id)
            return current[row.id]

        normal = certify_validation_gain(rows, anchor, lambda row: current[row.id], known=known)
        assert algorithm(rows, anchor, observe, known=known) == normal
