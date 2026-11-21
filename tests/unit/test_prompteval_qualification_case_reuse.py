from itertools import product

import pytest

from benchmarks.prompteval_qualification_case_reuse import audit_decision, qualify, schedule


PLAN = {'qualificationPolicy': 'extend-ties', 'minimumQualificationGain': 1, 'maximumExtensionRows': 4}


@pytest.mark.parametrize(('recycle', 'eligible'), ((False, []), (True, [3])))
def test_a_half_read_case_stays_retired(recycle, eligible):
    bank, touched, seen = [], set(), []

    def measure(prompt, case):
        seen.append(case)
        return prompt == 'new'

    selected, _, receipt = qualify('old', 'new', [0, 1, 2, 3], bank, touched, measure,
                                   plan=PLAN, seed=7, recycle=recycle)
    assert selected == 'new'
    assert receipt['qualificationLookups'] == 5
    assert seen == [0, 0, 1, 1, 2]
    assert touched == {0, 1, 2}
    assert bank == eligible


def test_unread_extension_returns_to_bank_without_double_charging():
    bank, touched = [0, 1, 2, 3, 4], set()
    selected, _, receipt = qualify('old', 'new', [5, 6, 7, 8], bank, touched,
                                   lambda prompt, case: case < 4 and prompt == 'new', plan=PLAN, seed=19, recycle=True)
    assert selected == 'new' and receipt['reserveAllocations'] == 1
    assert receipt['qualificationLookups'] == 13 and receipt['borrowedCasesRead'] == 3
    assert receipt['returnedExtensionCases'] == 1
    assert touched == {0, 1, 2, 5, 6, 7, 8}
    assert bank == [3, 4]


def test_idle_qualification_banks_every_case_and_never_evaluates():
    bank, touched = [0], set()

    def measure(*_):
        pytest.fail('Idle qualification read a case')

    selected, _, receipt = qualify('old', 'old', [1, 2], bank, touched, measure,
                                   plan=PLAN, seed=7, recycle=True)
    assert selected == 'old' and receipt['qualificationLookups'] == 0
    assert bank == [0, 1, 2] and not touched


def test_observed_case_cannot_return_in_a_later_reserve():
    with pytest.raises(ValueError, match='observed or duplicate case'):
        qualify('old', 'new', [2, 3], [1], {1}, lambda *_: False, plan=PLAN, seed=7, recycle=True)


def test_recycling_preserves_every_full_gate_on_two_base_and_two_reserve_cases():
    current, reserve = [0, 1], [2, 3]
    keys = tuple(product(('old', 'new'), (*current, *reserve)))
    for scores in product((False, True), repeat=len(keys)):
        values = dict(zip(keys, scores, strict=True))

        def measure(prompt, case):
            return values[prompt, case]

        expected, full, allocated = audit_decision('old', 'new', current, reserve, measure, threshold=1, seed=7)
        bank, touched = reserve.copy(), set()
        selected, evidence, receipt = qualify('old', 'new', current, bank, touched, measure,
                                              plan=PLAN, seed=7, recycle=True)
        assert selected == expected and evidence == full[:len(evidence)]
        assert receipt['reserveAllocations'] == allocated
        assert bank == [case for case in (*reserve, *current) if case not in touched]
        assert touched == {case for _, case, _ in evidence}


def test_shared_validation_remains_disjoint_from_every_qualification_panel():
    plan = {'cycles': 4, 'poolSize': 13, 'qualificationRowsPerCycle': 8, 'trainRows': 12, 'validationRows': 24}
    held = set(range(30))
    _, layouts = schedule(100, 100, held, 7, plan)
    qualification = [case for layout in layouts for case in layout['qualify']]
    assert len(set(qualification)) == len(qualification) == 32
    for layout in layouts:
        assert layout['validation'] == layouts[0]['validation']
        assert len(set(layout['train'] + layout['validation'])) == 36
        assert not set(layout['train'] + layout['validation']).intersection(held | set(qualification))
