from itertools import product

from benchmarks import recorded_remaining_validation_budget as study
from cpo import Observation, Row, select_pool


def test_a_partial_panel_can_certify_a_gain_only_after_protecting_the_incumbent():
    rows = tuple(Row(str(case), 'validation', critical=(case == 0)) for case in range(4))
    candidate = (True, True, True, True)
    leader, choice, old, paid = run_race(rows, ((True, False, False, False), candidate), cap=6)
    assert (leader, choice, len(old), len(paid)) == ('0', '1', 4, 6)
    assert paid['1', '0'].passed
    _, blocked, _, paid = run_race(rows, ((True, False, False, False), (False, *candidate[1:])), cap=6)
    assert blocked == '0' and len(paid) == 5


def test_remainder_never_retries_a_paid_challenger_or_exceeds_the_original_cap():
    rows = tuple(Row(str(case), 'validation', critical=(case == 1)) for case in range(3))
    for grades in product((False, True), repeat=9):
        board = (grades[:3], grades[3:6], grades[6:])
        for cap in range(3, 10):
            leader, choice, old, paid = run_race(rows, board, cap)
            seen = {prompt for prompt, _ in old}
            assert all(prompt not in seen for prompt, _ in paid.keys() - old.keys())
            if choice != leader:
                certified = sum(reply.passed for (prompt, _), reply in paid.items() if prompt == choice)
                assert certified > sum(board[int(leader)])
                if board[0][1]:
                    assert paid[choice, '1'].passed


def test_hindsight_headroom_requires_a_fundable_certificate_and_independent_gain():
    cells = {
        'start': [(grade, None, False) for grade in (1, 0, 0, 0, 0)],
        'valid': [(grade, None, False) for grade in (1, 1, 0, 1, 1)],
        'fails-proof': [(grade, None, False) for grade in (1, 1, 1, 0, 1)],
        'critical-loss': [(grade, None, False) for grade in (0, 1, 1, 1, 1)],
    }
    roster = tuple(cells)[1:]
    args = cells, 'start', roster, ([], [0, 1, 2], [3], [4]), 13
    assert not study.hindsight_headroom(args, ('start', roster, 1, (0,)), baseline_passes=0)
    result = study.hindsight_headroom(args, ('start', roster, 2, (0,)), baseline_passes=0)
    assert result == {'trialsWithFundableCertificate': 1, 'trialsWithFundableQualifiedCertificate': 1,
                      'extraPassesWithHindsight': 1}
    rejected = study.hindsight_headroom(args, ('start', roster[1:], 2, (0,)), baseline_passes=0)
    assert rejected['trialsWithFundableCertificate'] == 1 and rejected['extraPassesWithHindsight'] == 0


def run_race(rows, board, cap):
    prompts = tuple(map(str, range(len(board))))
    ledger = {}

    def read(prompt, row):
        key = prompt, row.id
        assert key not in ledger and len(ledger) < cap
        ledger[key] = Observation(board[int(prompt)][int(row.id)], {})
        return ledger[key]

    leader = select_pool(prompts, rows, read, metric_limit=cap, adaptive_rejection=True).prompt
    before = dict(ledger)
    chosen = study.finish_validation(prompts[0], leader, prompts[1:], rows, read, ledger, cap)
    return leader, chosen, before, ledger
