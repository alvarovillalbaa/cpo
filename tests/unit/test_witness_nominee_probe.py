import pytest

from benchmarks import witness_nominee_probe as study


def test_probe_prefers_the_cheapest_shared_case_with_a_possible_win():
    roster = {'nominee': {'validation': [9, 10, 11, 12]}, 'rival': {'validation': [10, 11, 12]}}
    paid = {('nominee', 10): True, ('nominee', 12): False, ('rival', 9): True}
    calls = []

    def reply(prompt, case):
        calls.append((prompt, case))
        return True

    assert study.probe('nominee', paid, roster, reply) == ('rival', 1, True)
    assert calls == [('rival', 12)]


def test_losing_probe_retains_nominee_and_charges_both_reads():
    roster = {'nominee': {'validation': [1]}, 'rival': {'validation': [1]}}
    captured = []

    def reply(prompt, case):
        captured.append((prompt, case))
        return True

    assert study.probe('nominee', {('rival', 2): True}, roster, reply) == ('nominee', 2, True)
    assert captured == [('nominee', 1), ('rival', 1)]


def test_proof_limit_never_dispatches_the_unfunded_reply():
    calls = []

    def reply(prompt, case):
        calls.append((prompt, case))
        return prompt == 'nominee'

    plan = {'qualificationPolicy': 'extend-ties', 'maximumExtensionRows': 0, 'minimumQualificationGain': 1}
    result = study.admit('start', 'nominee', [0, 1, 2], [], reply,
                         plan=plan, seed=0, recycle=False, remaining=1)
    assert result == ('start', 1, True)
    assert len(calls) == 1


def test_probe_refuses_overlapping_qualification_cases():
    nomination = study.earlier.Nomination('1', 1, {('1', 0): True})
    layouts = ({'validation': [0], 'qualify': [0], 'alternatives': ['1']},)
    with pytest.raises(ValueError, match='exclude every admission'):
        study.outcomes([], set(), '0', layouts, {}, 'retire-assigned', nomination)
