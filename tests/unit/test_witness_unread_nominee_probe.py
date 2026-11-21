import pytest

from benchmarks.witness_unread_nominee_probe import audit_reach, offer, probe


def test_probe_offer_prefers_a_shared_miss_and_never_rebuys_a_paid_grade():
    layout = {'validation': [1, 2], 'alternatives': ['nominee', 'paid', 'unread']}
    evidence = {('nominee', 1): False, ('nominee', 2): False, ('start', 2): False, ('paid', 2): True}

    assert offer('start', 'nominee', layout, evidence, unread=True) == ('unread', 2)
    assert offer('start', 'nominee', layout, evidence, unread=False) == ('paid', 1)
    assert offer('start', 'nominee', layout, {('nominee', 1): True}, unread=True) is None


@pytest.mark.parametrize('passed', [False, True])
def test_a_single_new_grade_can_redirect_the_nomination(passed):
    evidence = {('nominee', 1): False}
    calls = []

    def evaluate(prompt, case):
        calls.append((prompt, case))
        return passed

    chosen, updated = probe('nominee', ('rival', 1), evaluate, evidence)

    assert chosen == ('rival' if passed else 'nominee')
    assert calls == [('rival', 1)]
    assert updated == {('nominee', 1): False, ('rival', 1): passed}
    assert ('rival', 1) not in evidence


def test_reach_uses_both_current_prompts_as_the_comparison_floor():
    layouts = [{'alternatives': ['1', '2']}, {'alternatives': ['3']}]
    matrix = ('0000', '1000', '0100', '1100')
    reach = audit_reach(matrix, [0, 1], '0', '1', layouts, layouts[0]['alternatives'], {('2', 3): True})

    assert reach == {'strongerPaid': 0, 'strongerUnread': 1, 'strongerUnreadSameCycle': 0}
