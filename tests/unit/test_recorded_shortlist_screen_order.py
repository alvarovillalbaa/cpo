from collections import Counter
from itertools import product

from benchmarks import recorded_shortlist_screen_order as study
from cpo import Observation, Row


def test_pruned_pair_preserves_the_fully_observed_shortlist_on_every_four_prompt_board():
    roster = ('a', 'b', 'c', 'd')
    first, second = Row('miss', 'validation'), Row('pass', 'validation')
    skipped = 0
    for bits in product((False, True), repeat=8):
        board = dict(zip(roster, zip(bits[::2], bits[1::2], strict=True), strict=True))
        for target, protect in product((1, 4, 6), (False, True)):
            ledger, audit = {}, Counter()

            def observe(prompt, row):
                key = prompt, row.id
                assert key not in ledger
                ledger[key] = Observation(board[prompt][row == second], {})
                return ledger[key]

            protected = {second.id} if protect else set()
            selected = study.screen_finalists(roster, first, second, target, 6, protected, observe, ledger, audit)
            eligible = [prompt for prompt in roster if sum(board[prompt]) + 4 >= target
                        and (not protect or board[prompt][1])]
            expected = sorted(eligible, key=lambda prompt: (sum(board[prompt]), board[prompt][0]), reverse=True)[:2]
            assert selected == expected
            assert audit['screenLookups'] == len(ledger)
            skipped += audit['skippableSecondWitnesses']
    assert skipped > 0


def test_one_witness_reserves_three_slots_in_stable_paid_rank():
    roster = ('a', 'b', 'c', 'd', 'e')
    row = Row('miss', 'validation')
    ledger, audit = {}, Counter()

    def observe(prompt, case):
        key = prompt, case.id
        ledger[key] = Observation(prompt in ('b', 'd'), {})
        return ledger[key]

    assert study.screen_finalists(roster, row, None, 3, 6, set(), observe, ledger, audit) == ['b', 'd', 'a']
    assert audit['screenLookups'] == 5
