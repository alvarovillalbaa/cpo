from dataclasses import replace

import pytest

from cpo import Row
from cpo.halving.funded_admission import qualify_with_funded_retry
from cpo.rotating_witness.episode import WitnessCycle


def cycle(prompt, *case_ids):
    return WitnessCycle((prompt,), (Row('validation', 'task'),), tuple(Row(case, 'task') for case in case_ids))


def test_exact_rejection_with_a_used_tie_panel_moves_the_paid_rival_to_a_fresh_panel():
    cycles = (cycle('rival', 'r1', 'r2'), cycle('first', 'f1', 'f2'), cycle('unpaid', 'x1', 'x2'))
    paid = {('old', 'validation'): False, ('rival', 'validation'): True}
    calls = []

    def grade(prompt, row, repeat):
        calls.append((prompt, row.id, repeat))
        return (prompt == 'old' and row.id == 'r1') or (prompt == 'rival' and row.id in ('x1', 'x2'))

    result = qualify_with_funded_retry('old', 'first', cycles, grade, paid, evaluation_limit=12,
                                       minimum_retry_lookups=3, maximum_extension_rows=1)

    assert result.prompt == result.retry_candidate == 'rival'
    assert result.first.status == 'rejected' and result.first.used_reserve is True
    assert result.retry.status == 'promoted'
    assert {row.row_id for row in result.retry.observations} == {'x1', 'x2'}
    assert result.qualification_evaluations == len(calls) <= 12


@pytest.mark.parametrize(('cap', 'floor', 'supports_rival', 'expected'), [
    (0, 0, True, 'undecided'), (4, 0, True, 'rejected'), (12, 12, True, 'rejected'), (12, 0, False, 'rejected'),
])
def test_retry_gate_preserves_the_first_receipt(cap, floor, supports_rival, expected):
    cycles = (cycle('first', 'f1', 'f2'), cycle('rival', 'r1', 'r2'))
    paid = {('rival', 'validation'): True} if supports_rival else {}

    def grade(prompt, row, _repeat):
        assert row.id in ('f1', 'f2')
        return prompt == 'old'

    result = qualify_with_funded_retry('old', 'first', cycles, grade, paid, evaluation_limit=cap,
                                       minimum_retry_lookups=floor)

    assert result.prompt == 'old'
    assert result.first.status == expected
    assert result.retry is None and result.retry_candidate is None


def test_first_promotion_deploys_immediately_and_no_nominee_spends_nothing():
    cycles = (cycle('first', 'f1', 'f2'), cycle('rival', 'r1', 'r2'))

    def grade(prompt, row, _repeat):
        assert row.id in ('f1', 'f2')
        return prompt == 'first'

    result = qualify_with_funded_retry('old', 'first', cycles, grade, {('rival', 'validation'): True},
                                       minimum_retry_lookups=0)
    assert result.prompt == 'first' and result.first.status == 'promoted' and result.retry is None
    empty = qualify_with_funded_retry('old', None, cycles, grade, {}, minimum_retry_lookups=0)
    assert empty.prompt == 'old' and empty.first is None and empty.qualification_evaluations == 0


def test_rejects_validation_overlap_and_unenrolled_grades_before_any_callback():
    def grade(*_args):
        pytest.fail('Invalid inputs must be rejected before issuing a lookup')

    first = cycle('first', 'f1')
    with pytest.raises(ValueError, match='disjoint from validation'):
        qualify_with_funded_retry('old', 'first', [replace(first, validation=(Row('f1', 'task'),))],
                                  grade, {}, minimum_retry_lookups=0)
    with pytest.raises(ValueError, match='declared prompt and validation row'):
        qualify_with_funded_retry('old', 'first', [first], grade, {('rival', 'validation'): True},
                                  minimum_retry_lookups=0)
