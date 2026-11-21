import pytest

from benchmarks import recorded_certificate_allowance as study
from cpo import Observation, Row


def test_short_caps_keep_the_first_prompt_when_the_proof_cannot_fit():
    rows = tuple(Row(str(case), 'validation') for case in range(6))
    training = (Row('training', 'training'),)
    ledger = {('start', row.id): Observation(index < 2, {}) for index, row in enumerate(rows)}
    ledger.update({('first', row.id): Observation(True, {}) for row in rows[:3]})
    replies = {row.id: index != 3 for index, row in enumerate(rows)}

    def run(arm, cap):
        paid = ledger.copy()

        def observe(prompt, row):
            assert prompt == 'later'
            assert (prompt, row.id) not in paid
            paid[prompt, row.id] = Observation(replies[row.id], {})
            return paid[prompt, row.id]

        selected = study.search(arm, 'start', 'first', ('first', 'later'), rows, training, observe, paid,
                                cap=cap, extra=6)
        return selected, len(paid) - len(ledger)

    assert run('3-sixths-panel', 16) == (('first', False), 0)
    assert run('target-reads', 16) == (('first', False), 1)
    nominee, reads = run('target-plus-one', 16)
    assert nominee == ('later', True)
    assert reads == 5
    nominee, reads = run(study.FULL, 15)
    assert nominee == ('first', False)
    assert reads <= 4


@pytest.mark.parametrize(('old_grades', 'grades', 'selected', 'band'), [
    ((1, 0), (1, 0), 'first', 'sameDeployment'),
    ((1, 0), (1, 1), 'later', 'better'),
    ((1, 0), (0, 0), 'later', 'worse'),
    ((1, 0), (0, 1), 'later', 'changedWithEqualScore'),
])
def test_attribution_keeps_signed_lookup_and_pass_deltas(old_grades, grades, selected, band):
    initial = ({'paidLookups': 24, 'holdoutPasses': sum(old_grades)}, (0, 0, 0, 'first'), old_grades)
    result = ({'paidLookups': 23, 'holdoutPasses': sum(grades), 'extraValidationLookups': 2},
              (0, 0, 0, selected), grades)
    assert study.attribute(initial, result) == {
        f'{band}.trials': 1,
        f'{band}.heldoutPassDelta': sum(grades) - sum(old_grades),
        f'{band}.paidLookupDelta': -1,
        f'{band}.extraValidationLookups': 2,
    }
