from itertools import product

from benchmarks import recorded_certificate_lookahead_pruning as study
from cpo import Observation, Row


def test_pruning_preserves_the_original_nominee_on_every_unread_reply_pattern():
    rows = (Row('a', 'validation', True), Row('b', 'validation'), Row('c', 'validation'))
    train = (Row('train', 'training'),)
    candidates = ('first', 'second')
    paid = {('start', 'a'): True, ('start', 'b'): False, ('start', 'c'): False,
            ('first', 'a'): True, ('first', 'b'): True}
    pending = (('first', 'c'), *(('second', row.id) for row in rows))
    saved = 0
    for replies in product((False, True), repeat=len(pending)):
        possible = dict(zip(pending, replies, strict=True))
        for cap in range(7, 14):
            for extra in range(5):
                results = []
                for run in (study.original_search, study.prune):
                    ledger = {key: Observation(answer, {}) for key, answer in paid.items()}

                    def observe(prompt, row):
                        key = prompt, row.id
                        assert key not in ledger
                        ledger[key] = Observation(possible[key], {})
                        return ledger[key]

                    nominee, _ = run('start', 'first', candidates, rows, train, observe, ledger, cap=cap, extra=extra)
                    results.append((nominee, len(ledger)))
                (old, before), (new, after) = results
                assert new == old and after <= before
                saved += before - after
    assert saved > 0


def test_available_budget_keeps_the_later_candidates_training_reserve():
    rows = tuple(Row(case, 'validation') for case in 'abc')
    train = (Row('train', 'training'),)
    ledger = {('start', row.id): Observation(row.id == 'a', {}) for row in rows}
    ledger['second', 'b'] = Observation(True, {})
    rule = {'deadline': 10, 'target': 3, 'protected': {'a'}}
    assert not study.later_can_qualify('start', ('second',), rows, train, ledger, cap=8, **rule)
    assert study.later_can_qualify('start', ('second',), rows, train, ledger, cap=9, **rule)
    ledger['second', 'a'] = Observation(False, {})
    assert not study.later_can_qualify('start', ('second',), rows, train, ledger, cap=20, **rule)
