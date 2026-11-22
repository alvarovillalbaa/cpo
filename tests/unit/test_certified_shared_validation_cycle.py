from itertools import product

import pytest

from cpo import Observation, Row
from cpo.certified_shared_validation_cycle import _screen as certified_screen, run_certified_shared_validation_cycle
from cpo.shared_validation_cycle import _screen as eager_screen, run_shared_validation_cycle


def test_shortlist_certification_matches_every_three_case_matrix_and_round_boundary():
    rows = tuple(Row(str(i), 'validation') for i in range(3))
    incumbent, candidates = 'base', ('z', 'y', 'x')
    pairs = tuple(product((incumbent, *candidates), rows))

    for grades in product((False, True), repeat=len(pairs)):
        matrix = dict(zip(pairs, grades))

        def run(screen, cap, margin):
            paid = set()

            def evaluate(prompt, row):
                key = prompt, row
                assert key not in paid
                paid.add(key)
                return Observation(matrix[key], {})

            result, priors = screen(incumbent, candidates, rows, evaluate, cap, widths=(3, 2, 1), margin=margin)
            assert len(paid) == result.evaluations <= cap
            return (result.prompt, result.finalist, priors), paid

        for cap, margin in product(range(len(rows), 10), range(2)):
            expected, eager = run(eager_screen, cap, margin)
            actual, certified = run(certified_screen, cap, margin)
            assert actual == expected
            assert certified <= eager


@pytest.mark.parametrize('schedule,cap,saved', [('wide', 17, 7), ('wide', 9, 4), ('deep', 18, 3)])
def test_certification_preserves_the_qualification_receipt_and_leaves_the_savings_unspent(schedule, cap, saved):
    base, *candidates = 'base', 'z', 'y', 'x', 'w', 'v', 'u', 't', 's'
    rows = tuple(Row(str(i), 'validation') for i in range(6))
    qualification = tuple(Row(str(i), 'qualification') for i in range(6, 9))

    def run(cycle):
        return cycle(base, candidates, rows, qualification, lambda *_: Observation(True, {}),
                     metric_limit=cap, qualify=lambda prompt, *_: prompt != base, schedule=schedule)

    eager = run(run_shared_validation_cycle)
    certified = run(run_certified_shared_validation_cycle)
    assert eager.search.finalist == certified.search.finalist == candidates[0]
    assert eager.qualification == certified.qualification
    assert certified.promoted
    assert eager.search.evaluations - certified.search.evaluations == saved


def test_critical_validation_uses_the_same_strict_search_and_callback_order():
    rows = Row('miss', 'validation'), Row('critical', 'validation', critical=True)
    qualification = (Row('qualification', 'qualification'),)

    def run(cycle):
        reads = []

        def evaluate(prompt, row):
            reads.append((prompt, row.id))
            return Observation(prompt == 'winner' or row.critical, {})

        result = cycle('base', ('winner', 'other'), rows, qualification, evaluate, metric_limit=8,
                       qualify=lambda prompt, *_: prompt != 'base')
        assert result.promoted
        return result, reads

    assert run(run_certified_shared_validation_cycle) == run(run_shared_validation_cycle)
