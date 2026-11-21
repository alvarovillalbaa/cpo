from itertools import product

import pytest

from cpo import Row
from cpo.halving.qualification_budget import qualify_with_budget_lookahead


@pytest.mark.parametrize('prioritize_promotion', [False, True])
def test_every_scalar_board_preserves_the_full_decision_and_capped_promotions(prioritize_promotion):
    rows = tuple(Row(str(case), 'task') for case in range(3))
    reserve = tuple(Row(str(case), 'task') for case in range(3, 6))
    keys = [(prompt, row.id) for prompt in ('old', 'new') for row in (*rows, *reserve)]
    for bits in product((False, True), repeat=len(keys)):
        grades = dict(zip(keys, bits, strict=True))
        base_gain = sum(grades['new', row.id] - grades['old', row.id] for row in rows)
        gain = base_gain or sum(grades['new', row.id] - grades['old', row.id] for row in reserve)
        for cap in (5, 8, 12):
            calls = []

            def evaluate(prompt, row, repeat):
                assert repeat == 0
                calls.append((prompt, row.id))
                return grades[prompt, row.id]

            result = qualify_with_budget_lookahead('old', 'new', rows, evaluate, reserve=reserve,
                                                   evaluation_limit=cap, validation_counts=((3, 7), (4, 6)),
                                                   prioritize_promotion=prioritize_promotion)
            assert len(set(calls)) == len(calls) == len(result.observations) <= cap
            if result.status != 'undecided':
                assert result.prompt == ('new' if gain > 0 else 'old')
                assert result.used_reserve is (base_gain == 0)
            else:
                assert cap < 12 and result.prompt == 'old'


def test_cap_boundary_tracks_an_exact_base_tie_without_a_reserve_reply():
    base, reserve = (Row('base', 'task'),), (Row('reserve', 'task'),)
    before = qualify_with_budget_lookahead('old', 'new', base, lambda *_: True, reserve=reserve, evaluation_limit=1)
    after = qualify_with_budget_lookahead('old', 'new', base, lambda *_: True, reserve=reserve, evaluation_limit=2)
    assert (before.status, before.used_reserve) == ('undecided', None)
    assert (after.status, after.used_reserve) == ('undecided', True)


def test_rejects_overlapping_or_critical_rows_before_reading():
    row = Row('base', 'task')
    forbidden = lambda *_: pytest.fail('Invalid evidence reached evaluation')
    with pytest.raises(ValueError, match='distinct noncritical'):
        qualify_with_budget_lookahead('old', 'new', (row,), forbidden, reserve=(row,))
    with pytest.raises(ValueError, match='noncritical'):
        qualify_with_budget_lookahead('old', 'new', (Row('critical', 'task', critical=True),), forbidden)
