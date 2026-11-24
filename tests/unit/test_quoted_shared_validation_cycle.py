"""T2 exhaustive eager parity over tiny boolean validation matrices."""

from functools import partial
from itertools import product

from benchmarks.continuous_search_controls import HALVING, UNIFORM, screen as eager_screen
from cpo import Observation, Row
from cpo.quoted_shared_validation_cycle import _screen, run_quoted_shared_validation_cycle
from cpo.two_sided_certificate_cycle import run_two_sided_certificate_cycle


def test_skips_preserve_nominee_and_scores_at_each_funded_round_boundary():
    rows = tuple(Row(str(i), 'validation') for i in range(3))
    roster = ('a', 'b', 'c')
    pairs = tuple(product(('base', *roster), rows))
    for bits in product((False, True), repeat=len(pairs)):
        grades = dict(zip(pairs, bits, strict=True))

        def run(screen, cap):
            ledger = set()

            def evaluate(prompt, row):
                key = prompt, row
                assert key not in ledger
                ledger.add(key)
                return Observation(grades[key], {})

            result, counts = screen('base', roster, rows, evaluate, cap)
            assert len(ledger) == result.evaluations <= cap
            return (result.prompt, result.finalist, counts), ledger

        for mode, cap in product((UNIFORM, HALVING), (3, 4, 7, 9, 12)):
            before, paid = run(partial(eager_screen, mode=mode, width=len(roster)), cap)
            after, kept = run(partial(_screen, halve=mode == HALVING), cap)
            assert after == before
            assert kept <= paid


def test_perfect_incumbent_on_funded_prefix_avoids_every_challenger_read():
    validation = tuple(Row(str(i), 'validation') for i in range(4))
    qualification = (Row('q', 'qualification'),)
    reads = []

    def evaluate(prompt, row):
        reads.append((prompt, row))
        return Observation(True, {})

    result = run_quoted_shared_validation_cycle('base', ('a', 'b'), validation, qualification, evaluate,
                                                metric_limit=6, qualify=lambda *_: False)
    assert reads == [('base', row) for row in validation[:2]]
    assert result.search.evaluations == 2
    assert result.prompt == 'base'


def test_critical_validation_preserves_the_strict_two_sided_path():
    validation = (Row('miss', 'validation'), Row('guard', 'validation', critical=True))
    qualification = (Row('q', 'qualification'),)

    def run(cycle):
        reads = []

        def evaluate(prompt, row):
            reads.append((prompt, row.id))
            return Observation(prompt == 'safe' or (prompt == 'base' and row.critical), {})

        result = cycle('base', ('unsafe', 'safe'), validation, qualification, evaluate,
                       metric_limit=8, qualify=lambda prompt, *_: prompt == 'safe')
        return result, reads

    expected = run(run_two_sided_certificate_cycle)
    assert expected[0].prompt == 'safe'
    assert run(run_quoted_shared_validation_cycle) == expected
