import pytest

from benchmarks import witness_retry_funding as funding
from benchmarks.witness_admission_retry import Decision
from benchmarks.witness_paid_nominee_ranking import Nomination


def test_smoothed_signal_can_be_positive_without_a_paired_gain():
    grades = {('start', 0): True, ('start', 1): False, ('rival', 0): True, ('rival', 2): True}

    assert funding.paid_gains('start', 'rival', grades) == {'paired': False, 'smoothed': True}


@pytest.mark.parametrize('status', ['promoted', 'undecided'])
def test_only_exact_rejection_can_trigger_retry(status):
    first = Decision('start', 4, status)

    assert funding.gate_choices('start', first, 'rival', {}, 24) == ()


def test_retry_gates_depend_on_paid_evidence_and_the_first_receipt(monkeypatch):
    grades = {('start', 0): False, ('rival', 0): True}
    first = Decision('start', 13, 'rejected')
    second = Decision('rival', 24, 'promoted', retry=True, retry_lookups=11)
    reference = {funding.retry.BASE: first, funding.FULL: first, funding.EXACT: second}
    monkeypatch.setattr(funding, 'retry_outcomes', lambda *_: reference)
    layouts = [{'alternatives': ['nominee', 'rival']}]

    result = funding.outcomes([], [], 'start', layouts, {}, None, Nomination('nominee', 2, grades))

    assert result['paired-gain'] == result['smoothed-gain'] == second
    assert result['at-least-12'] == result['at-least-14'] == result['smoothed-gain-and-12'] == first
