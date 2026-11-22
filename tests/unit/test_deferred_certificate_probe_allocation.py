from benchmarks.deferred_certificate_probe_allocation import RACE, ROTATE, audit_headroom, run_variant
from benchmarks.recorded_deferred_certificate_cycle import execute_path
from cpo.paired_order_certificate_cycle import run_paired_order_certificate_cycle


def test_rotating_probe_recovers_a_fundable_challenger_after_first_witness_failure():
    cells = {'start': (0, 0, 1, 0, 0), 'first': (0, 0, 0, 0, 0), 'next': (0, 1, 1, 1, 1)}
    roles = (), (0, 1, 2), (3,), (4,)
    roster = ('first', 'next')
    args = cells, 'start', roster, roles, 0, 7, 1
    baseline, paid = execute_path(run_paired_order_certificate_cycle, *args)
    rotated, rotated_paid = run_variant(ROTATE, args)

    assert baseline.prompt == 'start'
    assert rotated.prompt == 'next'
    assert rotated.search.evaluations == 7
    assert rotated_paid['validation', 'next', '1'] is True
    assert audit_headroom(cells, 'start', roster, roles, 1, 7, baseline, paid) == (
        'betterSharedWitnessWasProbed', 1,
    )


def test_race_reallocates_after_a_miss_before_the_original_proof_exhausts_the_reserve():
    cells = {'start': (0, 0, 1, 1, 0, 0), 'first': (1, 0, 0, 1, 0, 0), 'next': (1, 1, 1, 0, 1, 1)}
    roles = (), (0, 1, 2, 3), (4,), (5,)
    args = cells, 'start', ('first', 'next'), roles, 0, 9, 1
    baseline, _ = execute_path(run_paired_order_certificate_cycle, *args)
    raced, paid = run_variant(RACE, args)

    assert baseline.prompt == 'start'
    assert raced.prompt == 'next'
    assert raced.search.evaluations == 9
    assert [key for key in paid if key[0] == 'validation' and key[1] != 'start'] == [
        ('validation', 'first', '0'), ('validation', 'next', '0'), ('validation', 'first', '1'),
        ('validation', 'next', '1'), ('validation', 'next', '2'),
    ]
