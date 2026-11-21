import pytest

from benchmarks import witness_no_nominee_miss as witness
from benchmarks.witness_admission_retry import Decision


def test_known_miss_order_and_peer_order_never_reuse_a_candidate_grade():
    evidence = {('old', 1): False, ('old', 2): False, ('old', 3): False, ('rival', 1): False,
                ('other', 3): True, ('other', 4): True}

    assert witness.choose_cases('old', 'rival', [1, 2, 3, 4], evidence) == (2, 3)
    assert witness.choose_cases('old', 'rival', [1, 4], evidence) is None


@pytest.mark.parametrize('passed', [False, True])
def test_probe_is_always_charged_and_a_pass_funds_only_the_remaining_proof(passed):
    evidence = {('old', 1): False}
    calls = []

    def grade(prompt, case):
        calls.append((prompt, case))
        return passed

    def prove(prompt, updated, cap):
        assert passed and updated == {**evidence, ('rival', 1): True}
        assert cap == witness.CAP - 1
        return Decision(prompt, cap, 'promoted')

    result, admitted = witness.screen('old', 'rival', 1, grade, evidence, prove)

    assert calls == [('rival', 1)]
    assert admitted is passed
    assert result.lookups == (witness.CAP if passed else 1)
    assert result.prompt == ('rival' if passed else 'old')


def test_invalid_paired_probe_leaves_the_ledger_untouched():
    evidence = {('old', 1): True}

    def unexpected(*_args):
        pytest.fail('Invalid probe attempted a read')

    with pytest.raises(ValueError, match='known incumbent miss'):
        witness.screen('old', 'rival', 1, unexpected, evidence, unexpected)
