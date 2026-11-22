from collections import Counter
from itertools import product

from benchmarks import recorded_early_certificate_screen as study
from cpo import Observation, Row


def test_minimum_reserve_can_reach_a_later_certifiable_challenger():
    rows = tuple(Row(str(case), 'validation', critical=(case == 1)) for case in range(6))
    board = ((False, True, False, False, False, False),
             (False,) * 6, (False,) * 6, (True, True, False, False, False, False))
    full, _, full_audit = screen(board, rows, 13, 'complete-panel')
    minimum, evidence, audit = screen(board, rows, 13, 'minimum-proof')
    assert full == '0' and full_audit['screenLookups'] == 2
    assert minimum == '3' and audit['screenLookups'] == 3 and audit['certificateLookups'] == 1
    assert evidence['3', '0'].passed and evidence['3', '1'].passed


def test_a_partial_certificate_can_pass_independent_qualification():
    splits = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 24)))
    validation = {'start': (0, 1, 0, 0, 0, 0), 'first': (0,) * 6, 'second': (0,) * 6,
                  'later': (1, 1, 1, 0, 0, 0)}
    cells = {prompt: [(grade, None, False) for grade in (0,) * 10 + grades + (int(prompt == 'later'),) * 8]
             for prompt, grades in validation.items()}
    point, trace, grades, audit = study.trial((cells, 'start', ('first', 'second', 'later'), splits, 7),
                                              'minimum-proof', 13)
    assert trace[2:4] == ('later', 'later') and grades == (1,) * 4
    assert audit['certificateLookups'] == 1 and point['searchLookups'] == 10
    assert 0 < point['qualificationLookups'] <= 8


def test_every_small_screen_stays_within_budget_and_certifies_its_nominee():
    rows = tuple(Row(str(case), 'validation', critical=(case == 1)) for case in range(3))
    for grades in product((False, True), repeat=9):
        board = (grades[:3], grades[3:6], grades[6:])
        for cap, method in product(range(3, 10), study.FUNDING):
            nominee, paid, audit = screen(board, rows, cap, method)
            assert len(paid) == len(rows) + audit['screenLookups'] + audit['certificateLookups']
            if nominee != '0':
                assert sum(reply.passed for (prompt, _), reply in paid.items() if prompt == nominee) > sum(board[0])
                if board[0][1]:
                    assert paid[nominee, '1'].passed


def screen(board, rows, cap, method):
    candidates = tuple(str(index) for index in range(1, len(board)))
    ledger, counts = {}, Counter()

    def observe(prompt, row):
        key = prompt, row.id
        assert key not in ledger and len(ledger) < cap
        ledger[key] = Observation(board[int(prompt)][int(row.id)], {})
        return ledger[key]

    winner = study.select('0', candidates, rows, observe, ledger, cap=cap, funding=method, audit=counts)
    return winner, ledger, counts
