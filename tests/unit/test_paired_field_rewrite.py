"""Verify paid field bounds and preserve strict native float gates."""

from itertools import product

import pytest

from benchmarks.gepa_cached_opening import select_opening
from cpo import Observation, Row
from cpo.paired_field_rewrite import _separates_distinct_totals, _wins, select_paired_field_rewrite


def compare(rows, batch, old, new):
    fields = rows[0].fields
    weight = 1 << (len(rows) * fields).bit_length()
    denominator = weight + fields

    def score(matched, order):
        return sum((weight * (matched[int(case)] == fields) + matched[int(case)]) / denominator for case in order)

    ids = tuple(row.id for row in rows)
    paid = {('start', case) for case in ids}
    if all(value == fields for value in old):
        return 'start', paid
    paid.update(('rewrite', case) for case in batch)
    if score(new, batch) <= score(old, batch):
        return 'start', paid
    paid.update(('rewrite', case) for case in ids)
    cached_first = tuple(sorted(ids, key=lambda case: case not in batch))
    selected = 'rewrite' if score(new, cached_first) / len(ids) > score(old, ids) / len(ids) else 'start'
    return selected, paid


@pytest.mark.parametrize('priced', (False, True))
@pytest.mark.parametrize('certify_ties', (False, True))
def test_paid_reads_match_complete_gates_across_all_three_field_profiles(priced, certify_ties):
    rows = tuple(Row(str(i), 'archive', fields=3) for i in range(4))
    batch = ('2', '0')
    for values in product(range(4), repeat=8):
        outcomes = {'start': values[:4], 'rewrite': values[4:]}
        paid = []

        def evaluate(prompt, row):
            assert row is rows[int(row.id)]
            paid.append((prompt, row.id))
            matched = outcomes[prompt][int(row.id)]
            return Observation(matched == row.fields, {}, matched)

        expected, complete = compare(rows, batch, outcomes['start'], outcomes['rewrite'])
        def charge(prompt, row, _reply):
            assert paid[-1] == (prompt, row.id)
            return 1 + int(row.id) + (prompt == 'rewrite')

        assert select_paired_field_rewrite('start', 'rewrite', rows, batch, evaluate,
                                           observed_charge=charge if priced else None,
                                           certify_boundary_ties=certify_ties) == expected
        assert len(paid) == len(set(paid))
        assert set(paid) <= complete


def test_observed_charge_can_change_full_validation_order():
    rows = tuple(Row(str(i), 'archive', fields=1) for i in range(4))
    batch = ('2', '0')

    def read(charge):
        paid = []

        def evaluate(prompt, row):
            paid.append((prompt, row.id))
            passed = prompt == 'rewrite'
            return Observation(passed, {}, int(passed))

        assert select_paired_field_rewrite('start', 'rewrite', rows, batch, evaluate,
                                           observed_charge=charge) == 'rewrite'
        return paid

    start_first = read(lambda prompt, *_: 1 if prompt == 'start' else 10)
    rewrite_first = read(lambda prompt, *_: 1 if prompt == 'rewrite' else 10)
    assert start_first[:3] == rewrite_first[:3] == [('start', '2'), ('rewrite', '2'), ('start', '0')]
    assert start_first[3] == ('start', '1')
    assert rewrite_first[3] == ('rewrite', '0')
    assert read(lambda *_: None) == read(lambda *_: 0) == read(lambda *_: 1)


@pytest.mark.parametrize('invalid', (-1, 0.5, True))
def test_invalid_observed_charges_stop_before_another_read(invalid):
    rows = (Row('0', 'archive', fields=1), Row('1', 'archive', fields=1))
    paid = []

    def evaluate(prompt, row):
        paid.append((prompt, row.id))
        return Observation(False, {}, 0)

    with pytest.raises(ValueError, match='nonnegative integers'):
        select_paired_field_rewrite('start', 'rewrite', rows, ('0',), evaluate,
                                     observed_charge=lambda *_: invalid)
    assert paid == [('start', '0')]


def test_rounded_gain_survives_equal_integer_totals():
    rows = tuple(Row(str(i), 'archive', fields=7) for i in range(4))
    batch = ('2', '0')
    matched = {'start': (5, 0, 1, 0), 'rewrite': (6, 0, 0, 0)}

    def evaluate(prompt, row):
        return Observation(False, {}, matched[prompt][int(row.id)])

    assert sum(matched['start']) == sum(matched['rewrite'])
    assert compare(rows, batch, matched['start'], matched['rewrite'])[0] == 'rewrite'
    assert select_paired_field_rewrite('start', 'rewrite', rows, batch, evaluate) == 'rewrite'


def test_endpoint_tie_can_reject_without_paying_for_the_last_grade():
    scores = {('start', 'a'): 39, ('start', 'b'): 0, ('rewrite', 'a'): 0}
    reads = []

    def observe(prompt, case):
        reads.append((prompt, case))
        scores[prompt, case] = 39
        return 39

    assert not _wins('start', 'rewrite', ('a', 'b'), scores, observe, 39,
                     full_order=('b', 'a'), certify_boundary_ties=True)
    assert reads == ([] if _separates_distinct_totals(2, 39) else [('rewrite', 'b')])


@pytest.mark.parametrize('missing_grade', (0, 1))
def test_endpoint_tie_with_possible_rounded_gain_still_needs_the_last_grade(missing_grade):
    scores = {('start', 'a'): 5, ('start', 'b'): 1,
              ('rewrite', 'a'): 6, ('rewrite', 'b'): 0, ('rewrite', 'c'): 0}
    reads = []

    def observe(prompt, case):
        reads.append((prompt, case))
        scores[prompt, case] = missing_grade
        return missing_grade

    assert _wins('start', 'rewrite', ('a', 'b', 'c'), scores, observe, 39,
                 certify_boundary_ties=True) == (missing_grade == 0)
    assert reads == [('start', 'c')]


def test_endpoint_tie_can_already_prove_a_native_rounded_gain():
    scores = {('start', 'a'): 5, ('start', 'b'): 1, ('rewrite', 'a'): 6}
    reads = []

    def observe(prompt, case):
        reads.append((prompt, case))
        scores[prompt, case] = 0
        return 0

    assert _wins('start', 'rewrite', ('a', 'b'), scores, observe, 39, certify_boundary_ties=True)
    assert reads == ([] if _separates_distinct_totals(2, 39) else [('rewrite', 'b')])


def test_inconsistent_field_grades_fail_closed():
    rows = (Row('0', 'archive', fields=4), Row('1', 'archive', fields=5))
    with pytest.raises(ValueError, match='uniform positive field count'):
        select_paired_field_rewrite('start', 'rewrite', rows, ('0',), lambda *_: pytest.fail('Paid a read'))
    with pytest.raises(ValueError, match='must agree'):
        select_paired_field_rewrite('start', 'rewrite', rows[:1], ('0',), lambda *_: Observation(True, {}, 0))


def test_native_gepa_uses_the_rounded_tie_to_select_the_rewrite():
    pytest.importorskip('gepa')
    rows = tuple(Row(str(i), 'archive', fields=7) for i in range(4))
    groups = {'validation': [{'id': row.id, 'expected': dict.fromkeys(range(row.fields))}
                             for row in rows]}
    batch = []

    def probe(prompt, case):
        if prompt == 'rewrite':
            batch.append(case)
        return Observation(False, {}, 0)

    def native(evaluate):
        return select_opening('start', ('rewrite',), groups, evaluate,
                              cap=8, seed=17, width=1, minibatch_size=2)

    assert native(probe) == 'start' and len(set(batch)) == len(batch) == 2
    matched = {'start': dict(zip(batch, (1, 5), strict=True)),
               'rewrite': dict(zip(batch, (0, 6), strict=True))}

    def evaluate(prompt, case):
        return Observation(False, {}, matched[prompt].get(case, 0))

    assert native(evaluate) == 'rewrite'
    assert select_paired_field_rewrite('start', 'rewrite', rows, batch,
                                       lambda prompt, row: evaluate(prompt, row.id)) == 'rewrite'
