from itertools import product

import pytest

from benchmarks import recorded_validation_race_order as study
from cpo import Observation, Row, select_pool


@pytest.mark.parametrize('policy', study.POLICIES)
def test_funded_dispatch_orders_preserve_exact_ranking_and_critical_passes(policy):
    names = ('initial', 'a', 'b')
    rows = (Row('1', 'validation', True), Row('2', 'validation'), Row('3', 'validation'))
    keys = tuple((name, row.id) for name in names for row in rows)
    chronology = {'a': 1, 'b': 2}
    for bits in product((False, True), repeat=len(keys)):
        grading = dict(zip(keys, bits, strict=True))
        paid = set()

        def read(prompt, row):
            key = prompt, row.id
            assert key not in paid
            paid.add(key)
            return Observation(grading[key], {})

        actual, scouting = study.select(names[0], names[1:], rows, read, cap=9,
                                        policy=policy, chronology=chronology)
        expected = select_pool(names, rows, lambda name, row: Observation(grading[name, row.id], {}),
                               metric_limit=9, adaptive_rejection=True)
        assert actual == expected.prompt
        assert len(paid) <= 9
        assert scouting in (0, 2)


def test_recent_first_falls_back_to_the_seeded_score_tie_order():
    rows = (Row('1', 'validation'), Row('2', 'validation'))
    calls = []

    def read(prompt, row):
        calls.append((prompt, row.id))
        return Observation(prompt != 'initial', {})

    actual, _ = study.select('initial', ('a', 'b'), rows, read, cap=6, policy=study.RECENCY,
                             chronology={'a': 1, 'b': 2})
    assert calls[2][0] == 'b'
    assert actual == 'a'
