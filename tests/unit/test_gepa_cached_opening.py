import pytest

from benchmarks.gepa_cached_opening import select_opening
from cpo import Observation


@pytest.mark.parametrize('width', (1, 2))
def test_native_fixed_opening_reads_each_validation_pair_once(width):
    validation = [{'id': f'row-{i}', 'expected': {'value': i}} for i in range(4)]
    groups = {'validation': validation, 'train': [{'id': 'training', 'expected': {'value': 0}}]}
    paid = set()

    def evaluate(prompt, row):
        assert row != 'training'
        assert (prompt, row) not in paid
        paid.add((prompt, row))
        return Observation(prompt == 'rewrite', {}, int(prompt == 'rewrite'))

    selected = select_opening('start', ('rewrite', 'repair'), groups, evaluate,
                              width=width, minibatch_size=2, seed=3, cap=12)
    assert selected == 'rewrite'
    assert len(paid) <= 12


def test_native_fixed_opening_refuses_insufficient_paid_budget():
    with pytest.raises(ValueError, match='paid cap'):
        select_opening('start', ('rewrite', 'repair'), {'validation': [{'id': 'a'}]},
                       lambda *_: pytest.fail('Evaluation called'), width=2, minibatch_size=1, seed=3, cap=2)
