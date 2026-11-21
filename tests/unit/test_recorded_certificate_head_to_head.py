from itertools import product

from benchmarks import recorded_certificate_head_to_head as study
from cpo import Observation, Row


def run(rows, first_tail, challenger_bits, extra, *, paired):
    ledger = {('start', row.id): Observation(row.id == 'b', {}) for row in rows}
    ledger.update({('first', 'a'): Observation(True, {}), ('first', 'b'): Observation(True, {})})
    pending = {**dict(zip((('first', row.id) for row in rows[2:]), first_tail, strict=True)),
               **dict(zip((('later', row.id) for row in rows), challenger_bits, strict=True))}
    before = len(ledger)

    def observe(prompt, row):
        key = prompt, row.id
        assert key not in ledger
        ledger[key] = Observation(pending[key], {})
        return ledger[key]

    selected, _ = study.search_later('start', 'first', ('first', 'later'), rows, (Row('t', 'training'),),
                                     observe, ledger, cap=20, extra=extra, paired=paired)
    assert len(ledger) - before <= extra
    return selected


def test_paired_gate_demands_strict_improvement_over_the_first_candidate():
    rows = tuple(Row(name, 'validation') for name in 'abcd')
    challenger = (True, True, True, False)
    assert run(rows, (True, False), challenger, 6, paired=False) == 'later'
    assert run(rows, (True, False), challenger, 6, paired=True) == 'first'
    assert run(rows, (False, False), challenger, 6, paired=True) == 'later'


def test_all_observed_replacements_prove_paired_gain_and_keep_firsts_critical_pass():
    rows = (Row('a', 'validation', True), *(Row(name, 'validation') for name in 'bcd'))
    accepted = 0
    for bits in product((False, True), repeat=6):
        first, later = bits[:2], bits[2:]
        for extra in (4, 6, 8):
            chosen = run(rows, first, later, extra, paired=True)
            if chosen == 'later':
                accepted += 1
                assert sum(later) > 2 + sum(first)
                assert later[0]
    assert accepted > 0
