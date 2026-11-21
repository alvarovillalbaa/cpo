"""T2 checks for the added arm's request and attribution boundaries."""

import pytest

from benchmarks import grounded_staged_paired_opening_comparison as trial


def journal(handle, callback):
    limits = {'reflection': 3, 'evaluation': 56}
    return trial.Journal(handle, {'logicalLimitsByRole': limits, 'searchCap': 56, 'repeats': 1}, callback)


def test_paired_opening_can_only_reuse_a_committed_shared_opening(tmp_path):
    calls = []

    def respond(request):
        calls.append(request)
        return 'same recorded opening'

    with (tmp_path / 'wire.jsonl').open('x') as handle:
        wire = journal(handle, respond)
        request = {'task': 'ticket', 'role': 'reflection', 'instruction': 'opening', 'input': 'training only'}
        with pytest.raises(ValueError, match='reuse the exact shared opening'):
            wire.send(trial.ARM, request)
        assert not calls

        paid = wire.send('shared', request)
        assert wire.send(trial.ARM, request) == paid
    assert calls == [request]
    assert wire.physical['reflection'] == 1 and wire.search_uses['shared'] == [1]


def test_paired_opening_validation_cap_is_enforced_before_dispatch(tmp_path):
    calls = []

    def respond(request):
        calls.append(request)
        return '{}'

    cap = 3 * trial.comparison.staged.SPLITS['validation']
    request = {'task': 'ticket', 'role': 'evaluation', 'instruction': 'candidate'}
    with (tmp_path / 'wire.jsonl').open('x') as handle:
        wire = journal(handle, respond)
        for index in range(cap):
            wire.send(trial.ARM, {**request, 'input': str(index)})
        with pytest.raises(ValueError, match='sealed validation cap'):
            wire.send(trial.ARM, {**request, 'input': 'too many'})
    assert len(calls) == cap
