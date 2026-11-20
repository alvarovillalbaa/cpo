"""Verify paid field bounds and preserve strict native float gates."""

from itertools import product

import pytest

from benchmarks.gepa_cached_opening import select_opening
from cpo import Observation, Row
from cpo.paired_field_rewrite import select_paired_field_rewrite


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


def test_paid_reads_match_complete_gates_across_all_three_field_profiles():
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
        assert select_paired_field_rewrite('start', 'rewrite', rows, batch, evaluate) == expected
        assert len(paid) == len(set(paid))
        assert set(paid) <= complete


def test_rounded_gain_survives_equal_integer_totals():
    rows = tuple(Row(str(i), 'archive', fields=7) for i in range(4))
    batch = ('2', '0')
    matched = {'start': (5, 0, 1, 0), 'rewrite': (6, 0, 0, 0)}

    def evaluate(prompt, row):
        return Observation(False, {}, matched[prompt][int(row.id)])

    assert sum(matched['start']) == sum(matched['rewrite'])
    assert compare(rows, batch, matched['start'], matched['rewrite'])[0] == 'rewrite'
    assert select_paired_field_rewrite('start', 'rewrite', rows, batch, evaluate) == 'rewrite'


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
