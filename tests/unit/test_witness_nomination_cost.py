import pytest

from benchmarks import witness_nomination_cost as study
from cpo import Observation, Row


@pytest.mark.parametrize(('witness', 'qualification_miss'), ((False, True), (True, False), (True, True)))
def test_defer_precheck_without_changing_nomination_or_independent_proof(witness, qualification_miss):
    validation = tuple(Row(f'v{i}', 'validation') for i in range(2))
    proof = tuple(Row(f'q{i}', 'qualification') for i in range(4))

    def play(order):
        seen = []

        def evaluate(prompt, row):
            seen.append(('validation', prompt, row.id))
            return Observation(prompt != 'base' or not witness or row.id == 'v0', {})

        def qualify(prompt, row, repeat):
            assert repeat == 0
            seen.append(('qualification', prompt, row.id))
            return prompt != 'base' or not qualification_miss or row.id != 'q0'

        result = study.cycle(None, order, 'base', ('repair',), validation, proof, evaluate,
                             metric_limit=6, qualify=qualify, seed=0)
        assert len(seen) == result.search.evaluations + result.qualification_evaluations
        assert len(seen) == len(set(seen))
        return result, seen

    first, first_seen = play(study.VALIDATION_FIRST)
    second, second_seen = play(study.QUALIFICATION_FIRST)
    assert (first.prompt, first.search.finalist) == (second.prompt, second.search.finalist)
    expected = 'repair' if witness and qualification_miss else 'base'
    assert first.prompt == expected
    if not witness:
        assert all(role == 'validation' for role, *_ in first_seen)
        assert len(first_seen) < len(second_seen)
    elif not qualification_miss:
        assert all(role == 'qualification' for role, *_ in second_seen)
        assert len(second_seen) < len(first_seen)
    else:
        assert first.qualification == second.qualification
        assert len(first_seen) == len(second_seen)


def test_late_critical_case_leaves_the_complete_panel_to_the_original_policy():
    validation = (Row('v0', 'validation'), Row('v1', 'validation', critical=True))
    proof = (Row('q0', 'qualification'),)
    original = object()

    def fallback(incumbent, roster, rows, qualification, evaluate, *, metric_limit, qualify, seed):
        assert (incumbent, roster, rows, qualification, metric_limit) == ('base', ('repair',), validation, proof, 6)
        return original

    for order in study.ORDERS:
        assert study.cycle(fallback, order, 'base', ('repair',), validation, proof, None,
                           metric_limit=6, qualify=None, seed=0) is original
    assert study.defer_packaged(fallback, 'base', ('repair',), validation, proof, None,
                                metric_limit=6, qualify=None, seed=0) is original


def test_precheck_stays_in_place_for_the_fitted_opening_dispatcher():
    routes = study.settled._RUNNERS
    opening, uniform, halving = study.settled._ACTIONS
    original = dict(routes)
    with study.use_order(study.ORIGINAL_DEFERRED):
        assert routes[opening] is original[opening]
        assert routes[uniform] is not original[uniform]
        assert routes[halving] is not original[halving]
    assert routes == original


@pytest.mark.parametrize(('width', 'expected_proof_reads'), ((2, 1), (8, 0)))
def test_full_roster_guard_uses_the_screen_width(width, expected_proof_reads):
    candidates = tuple(f'candidate-{index}' for index in range(width))
    validation = tuple(Row(f'v{i}', 'validation') for i in range(3))
    proof = tuple(Row(f'q{i}', 'qualification') for i in range(4))
    uniform = study.settled._ACTIONS[1]
    with study.use_order(study.FULL_ROSTER_DEFERRED):
        result = study.settled._RUNNERS[uniform](
            'base', candidates, validation, proof, lambda *_: Observation(True, {}),
            metric_limit=19, qualify=lambda *_: False, seed=0,
        )
    assert result.search.finalist is None
    assert result.prompt == 'base'
    assert result.qualification_evaluations == expected_proof_reads
