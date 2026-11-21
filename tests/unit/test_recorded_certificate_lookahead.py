from benchmarks import recorded_certificate_lookahead as study
from cpo import Observation, Row


def test_lookahead_keeps_first_without_enough_reads_and_proves_a_later_two_pass_gain():
    rows = (Row('a', 'validation', True), Row('b', 'validation'), Row('c', 'validation'), Row('d', 'validation'))
    training = (Row('training', 'training'),)
    replies = {('start', row.id): row.id == 'a' for row in rows}
    replies.update({('first', 'a'): True, ('first', 'b'): True})
    for extra, expected in ((4, ('first', False)), (5, ('later', True))):
        ledger = {key: Observation(value, {}) for key, value in replies.items()}

        def observe(prompt, row):
            key = prompt, row.id
            assert key not in ledger
            ledger[key] = Observation(prompt == 'later', {})
            return ledger[key]

        assert study.search_for_stronger('start', 'first', ('first', 'later'), rows, training, observe, ledger,
                                         cap=20, extra=extra) == expected
        assert len(ledger) - len(replies) <= extra
        if expected[1]:
            assert ledger['later', 'a'].passed
            assert sum(reply.passed for (prompt, _), reply in ledger.items() if prompt == 'later') == 3


def test_lookahead_does_not_spend_the_training_reserve_or_search_an_impossible_gain():
    rows = tuple(Row(case, 'validation') for case in 'abc')
    training = (Row('training', 'training'),)
    ledger = {('start', row.id): Observation(row.id == 'a', {}) for row in rows}
    ledger.update({('first', 'a'): Observation(True, {}), ('first', 'b'): Observation(True, {})})

    def unexpected(*_):
        raise AssertionError('The candidate must keep its original training reserve')

    assert study.search_for_stronger('start', 'first', ('first',), rows, training, unexpected, ledger,
                                     cap=len(ledger) + 2, extra=6) == ('first', False)
    ledger['start', 'b'] = Observation(True, {})
    assert study.search_for_stronger('start', 'first', ('first',), rows, training, unexpected, ledger,
                                     cap=100, extra=6) == ('first', False)
