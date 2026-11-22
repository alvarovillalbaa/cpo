from benchmarks import recorded_paid_qualification_margin_route as study
from cpo import Observation, Row


def test_unread_candidate_cases_do_not_count_as_regressions():
    rows = tuple(Row(str(case), 'validation') for case in range(6))
    paid = {('start', row.id): Observation(case < 4, {}) for case, row in enumerate(rows)}
    paid['new', '4'] = Observation(True, {})
    assert not study.use_two(study.REGRESSION, 'start', 'new', rows, paid)
    assert study.use_two(study.HIGH_INCUMBENT, 'start', 'new', rows, paid)
    paid['new', '2'] = Observation(False, {})
    assert study.use_two(study.REGRESSION, 'start', 'new', rows, paid)
    assert not study.use_two(study.REGRESSION, 'start', 'start', rows, paid)


def test_route_changes_only_the_independent_proof_target():
    layout = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 24)))
    validation = {'start': (0, 0, 1, 1, 1, 1), 'challenger': (1, 1, 1, 1, 1, 1)}
    proof = {'start': (0,) * 4, 'challenger': (1, 0, 0, 0)}
    cells = {label: [(grade, None, False) for grade in (0,) * 10 + grades + proof[label] + (1,) * 4]
             for label, grades in validation.items()}
    args = cells, 'start', ('challenger',), layout, 7
    (ordinary, first, _, _), before = study.routed_trial(args, study.REGRESSION, 13)
    (strong, second, _, _), after = study.routed_trial(args, study.HIGH_INCUMBENT, 13)
    assert not before and after
    assert first[:3] == second[:3] and first[2:4] == ('challenger', 'challenger')
    assert second[3] == 'start' and ordinary['searchLookups'] == strong['searchLookups']
