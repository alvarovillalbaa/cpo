"""T2 mock grade traces for the exact routing shortcut."""

from itertools import product

from benchmarks.short_circuit_archive_routing import optimized_cycle, routing, transfer
from cpo import Observation, Row


def execute(cycle, actions, prefix, first_validation):
    validation = tuple(Row(f'v{i}', 'validation') for i in range(6))
    qualification = tuple(Row(f'q{i}', 'qualification') for i in range(4))
    paid = {}

    def charge(prompt, row, result):
        key = prompt, row.id
        assert key not in paid
        paid[key] = result
        return result

    def evaluate(prompt, row):
        return Observation(charge(prompt, row, first_validation if prompt == 'base' else True), {})

    def qualify(prompt, row, _):
        return charge(prompt, row, prefix[int(row.id[1:])] if prompt == 'base' else True)

    options = dict(metric_limit=19, qualify=qualify, minimum_gain=1, seed=17)
    fallback = 'incumbent-first'
    if cycle is optimized_cycle:
        options.update(actions=actions, fallback=fallback)
    else:
        options.update(model=routing.PROBE, choose=lambda key: actions.get(key, fallback))
    decision = cycle('base', ('other',), validation, qualification, evaluate, **options)
    assert len(paid) == decision.search.evaluations + decision.qualification_evaluations
    return decision, paid


def test_truncates_a_tail_that_can_only_retain_and_leaves_gain_bounds_from_paid_grades():
    retain = transfer.RETAIN
    cutoff = {'3/0': retain, '3/1': retain, '4/0': retain, '4/1': retain}
    for late in product((False, True), repeat=2):
        result, ledger = execute(optimized_cycle, cutoff, (True, True, *late), True)
        assert result.prompt == 'base' and result.search.finalist is None
        assert tuple(ledger) == (('base', 'q0'), ('base', 'q1'))
        assert result.qualification.upper_gain == 2


def test_keeps_later_routes_when_some_intermediate_contexts_always_retain():
    retain = transfer.RETAIN
    skipped = {'2/0': retain, '2/1': retain, '3/0': retain, '3/1': retain}
    result, ledger = execute(optimized_cycle, skipped, (True, True, True, False), False)
    assert result.promoted
    assert ('base', 'q3') in ledger


def test_reproduces_every_nominee_and_admitted_proof_for_mock_grade_profiles():
    retain = transfer.RETAIN
    tables = ({}, {'1/0': retain, '1/1': 'certified-wide', '3/0': retain, '3/1': retain},
              {'4/0': retain, '4/1': retain}, {f'{i}/{grade}': retain for i, grade in product(range(1, 5), (0, 1))})
    for table, prefix, grade in product(tables, product((False, True), repeat=4), (True, False)):
        before, old = execute(routing.profiled_cycle, table, prefix, grade)
        after, new = execute(optimized_cycle, table, prefix, grade)
        assert (after.prompt, after.search.finalist) == (before.prompt, before.search.finalist)
        assert new.items() <= old.items()
        if before.search.finalist is not None:
            assert before.qualification == after.qualification
