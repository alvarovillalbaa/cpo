import pytest

from benchmarks.recorded_independent_holdout import independent_rows


def test_case_ids_cannot_hide_development_input_reuse():
    development = {'id': 'validation-1', 'input': 'Record validation-1. Shared input'}
    holdout = {'id': 'holdout-1', 'input': 'Record holdout-1. Shared input'}
    with pytest.raises(ValueError, match='duplicates a development input'):
        independent_rows({'train': [], 'validation': [development], 'holdout': [holdout]})


def test_independent_holdout_returns_only_the_scored_partition():
    train = {'id': 'train', 'input': 'Train only'}
    holdout = {'id': 'holdout', 'input': 'Different input', 'critical': True}
    assert independent_rows({'train': [train], 'validation': [], 'holdout': [holdout]}) == {'holdout': holdout}
