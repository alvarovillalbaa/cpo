import pytest

from benchmarks import recorded_one_failure_screen_transfer as study


def test_reserve_can_finish_after_one_failed_reply():
    splits = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 24)))
    roster = tuple(str(index) for index in range(8))
    validation = {'start': (0, 1, 0, 0, 0, 0), **dict.fromkeys(roster, (0,) * 6), '0': (1, 0, 0, 1, 0, 0)}
    cells = {prompt: [(grade, None, False) for grade in (0,) * 10 + grades + (int(prompt == '0'),) * 8]
             for prompt, grades in validation.items()}
    args = cells, 'start', roster, splits, 7
    _, original, _, minimum = study.prior.trial(args, 'minimum-proof', study.CAP)
    changed, trace, held, reserved = study.one_failure_trial(args)
    assert original[2:4] == ('start', 'start') and trace[2:4] == ('0', '0')
    assert (minimum['screenLookups'], reserved['screenLookups'], reserved['certificateLookups']) == (6, 5, 2)
    assert changed['searchLookups'] == study.CAP and held == (1,) * 4


def test_transfer_rejects_misaligned_or_unpaired_panels():
    def panel(subject, model, order='order'):
        return {'subject': subject, 'model': model, 'caseOrderSha256': order, 'correctness': ['01' * 15] * 100}

    donor = [('MMLU', 'seen', 'old-model')]
    rows = [panel('new', 'a'), panel('new', 'b'), panel('seen', 'c'), panel('seen', 'd')]
    assert [(subject, model) for subject, model, _ in study.enroll(rows, donor)] == [('new', 'a'), ('new', 'b')]
    with pytest.raises(ValueError, match='aligned'):
        study.enroll([panel('new', 'a'), panel('new', 'b', 'wrong')], donor)
    with pytest.raises(ValueError, match='both'):
        study.enroll([panel('new', 'a'), panel('new', 'old-model')], donor)
