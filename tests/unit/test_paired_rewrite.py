"""Check both paired gain gates over all binary profiles on four cases."""

from itertools import product

import pytest

from cpo import Observation, Row
from cpo.paired_rewrite import select_paired_rewrite


def test_paid_reads_are_a_subset_of_complete_native_gates():
    validation = tuple(Row(str(i), f'family-{i}', critical=True) for i in range(4))
    batch = ('2', '0')
    for bits in product((False, True), repeat=8):
        outcomes = dict(zip(product(('start', 'rewrite'), (row.id for row in validation)), bits, strict=True))
        paid = []

        def evaluate(prompt, row):
            assert row is validation[int(row.id)]
            paid.append((prompt, row.id))
            return Observation(outcomes[prompt, row.id], {})

        old = sum(bits[:4])
        new = sum(bits[4:])
        gain = sum(int(outcomes['rewrite', case]) - int(outcomes['start', case]) for case in batch)
        expected = 'rewrite' if gain > 0 and new > old else 'start'
        assert select_paired_rewrite('start', 'rewrite', validation, batch, evaluate) == expected
        complete = {('start', row.id) for row in validation}
        if old < len(validation):
            complete.update(('rewrite', case) for case in batch)
        if gain > 0:
            complete.update(('rewrite', row.id) for row in validation)
        assert len(paid) == len(set(paid))
        assert set(paid) <= complete


def test_minibatch_requires_distinct_known_cases_before_reading():
    validation = (Row('known', 'family'),)
    for batch in ((), ('unknown',), ('known', 'known')):
        with pytest.raises(ValueError, match='nonempty subset'):
            select_paired_rewrite('start', 'rewrite', validation, batch, lambda *_: pytest.fail('Read a case'))
