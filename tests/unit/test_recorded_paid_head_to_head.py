from benchmarks import recorded_paid_head_to_head as study
from cpo import Observation, Row


def test_same_case_tie_must_prove_strict_gain_and_preserve_critical_passes():
    rows = tuple(Row(case, 'validation', critical=case == 'a') for case in 'abcdef')
    boards = {'start': dict(zip('abcdef', (1, 1, 0, 0, 0, 0), strict=True)),
              'first': dict(zip('abcdef', (1, 1, 1, 1, 0, 0), strict=True)),
              'alternative': {'a': 1, 'b': 0, 'c': 0, 'e': 1, 'f': 1},
              'missing-critical': {'b': 1, 'c': 0, 'd': 0, 'e': 1, 'f': 1},
              'unproven': {'a': 1, 'e': 1}}
    ledger = {(prompt, case): Observation(bool(passed), {}) for prompt, grades in boards.items()
              for case, passed in grades.items()}
    args = 'start', 'first', tuple(boards)[1:], rows, ledger
    assert study.comparisons(*args, study.TIE) == {'alternative': (0, -2, 3, 5)}
    assert study.comparisons(*args, study.PRESERVE) == {}


def test_paid_tie_can_replace_an_exact_winner_without_any_extra_validation():
    cells = {prompt: tuple((grade, None, False) for grade in outcomes) for prompt, outcomes in {
        'start': (0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0),
        'first': (0, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0),
        'alternative': (0, 0, 0, 0, 1, 0, 0, 0, 1, 1, 1, 1, 1),
    }.items()}
    cohorts = ([0, 1, 2, 3], [4, 5, 6, 7, 8, 9], [10, 11], [12])
    args = (cells, 'start', ('first', 'alternative'), cohorts, 31, 40)
    old, trace, _, _ = study.prior.run_trial(*args, ())
    assert trace[2:4] == ('first', 'start')
    for mode in study.MODES:
        point, trace, grades, allowed = study.run_trial(*args, mode)
        assert allowed == ('alternative',)
        assert trace[2:4] == ('alternative', 'alternative') and grades == (1,)
        assert point['searchLookups'] == old['searchLookups']
        assert point['qualificationLookups'] <= 4
