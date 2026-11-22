import pytest

from cpo import Observation, Row
from cpo.prechecked_certificate_cycle import run_prechecked_certificate_cycle


def test_a_perfect_incumbent_skips_validation_and_keeps_its_paid_prefix():
    result = run_prechecked_certificate_cycle(
        'start', ('candidate',), (Row('v', 'validation'),), (Row('q1', 'proof'), Row('q2', 'proof')),
        lambda *_: pytest.fail('Validation must not run after a perfect qualification panel'),
        metric_limit=2, qualify=lambda *_: True,
    )
    assert result.prompt == 'start' and result.search.evaluations == 0
    assert result.qualification_evaluations == 2 and result.qualification.upper_gain == 0


def test_one_paid_miss_is_credited_for_either_qualification_margin():
    validation = tuple(Row(f'v{index}', 'validation') for index in range(6))
    proof = tuple(Row(f'q{index}', 'proof') for index in range(4))
    for minimum_gain in (1, 2):
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(prompt == 'candidate', {})

        def qualify(prompt, row, repeat):
            assert repeat == 0
            calls.append((prompt, row.id))
            return prompt == 'candidate' and row.id == 'q0'

        result = run_prechecked_certificate_cycle('start', ('candidate',), validation, proof, evaluate,
                                                   metric_limit=13, qualify=qualify, minimum_gain=minimum_gain)
        assert calls[0] == ('start', 'q0') and len(calls) == len(set(calls))
        assert result.search.prompt == 'candidate' and result.search.evaluations == 7
        assert result.promoted == (minimum_gain == 1)
        assert result.qualification_evaluations <= 8
        assert result.search.evaluations + result.qualification_evaluations == len(calls)


def test_fallback_certificate_preserves_critical_qualification_passes():
    proof = (Row('q0', 'proof'), Row('q1', 'proof', critical=True), Row('q2', 'proof'))
    seen = set()

    def qualify(prompt, row, repeat):
        assert (prompt, row.id) not in seen
        seen.add((prompt, row.id))
        return (row.id == 'q1') if prompt == 'start' else row.id != 'q1'

    result = run_prechecked_certificate_cycle(
        'start', ('candidate',), (Row('v', 'validation'),), proof,
        lambda prompt, _: Observation(prompt == 'candidate', {}),
        metric_limit=2, qualify=qualify,
    )
    assert result.search.prompt == 'candidate' and result.prompt == 'start'
    assert result.qualification_evaluations == len(seen)
    assert result.qualification.observations[0].row_id == 'q0'


def test_overlapping_cases_fail_before_any_paid_reply():
    row = Row('shared', 'case')
    with pytest.raises(ValueError, match='disjoint'):
        run_prechecked_certificate_cycle('start', ('candidate',), (row,), (row,), pytest.fail,
                                         metric_limit=2, qualify=pytest.fail)
