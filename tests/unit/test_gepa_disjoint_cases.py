import pytest

from benchmarks import gepa_disjoint_cases, opening_screen_typed
from cpo import Observation


def test_disjoint_case_ids_keep_training_replies_out_of_validation():
    groups = {split: [{'id': f'{split}-{i}', 'expected': {'value': 0}} for i in range(4)]
              for split in ('train', 'validation')}
    paid = []

    def evaluate(prompt, case):
        paid.append((prompt, case))
        passed = (prompt == 'rewrite' and case.startswith('train-')) or (prompt, case) == ('start', 'validation-0')
        return Observation(passed, {}, int(passed))

    def reflect(*_):
        pytest.fail('An already supplied rewrite needs no new proposal')

    choices = []
    for select in (opening_screen_typed.gepa_select, gepa_disjoint_cases.select):
        paid.clear()
        result = select('start', ('rewrite', 'repair'), groups, evaluate, reflect, cap=12, seed=3, width=1)
        true_validation_reads = sum(prompt == 'rewrite' and case.startswith('validation-') for prompt, case in paid)
        choices.append((result, true_validation_reads))
    assert choices == [('rewrite', 2), ('start', 4)]


def test_disjoint_loader_refuses_overlapping_ids_before_search():
    identical = [{'id': 'same'}]
    with pytest.raises(ValueError, match='must be disjoint'):
        gepa_disjoint_cases.select('start', ('rewrite',), {'train': identical, 'validation': identical},
                                   lambda *_: pytest.fail('Evaluation called'), lambda *_: 'rewrite')
