import pytest

from benchmarks.deferred_certificate_subject_ceiling import reuse_native_search


def test_reused_search_replays_observations_and_budget_checks_in_order():
    optimizations = []

    def optimize(start, roster, training, validation, observe, spent, *, paid_limit, batched, seed):
        optimizations.append(paid_limit)
        assert spent() == 0
        assert observe(start, validation[0]) is False
        assert spent() == 1
        assert observe(roster[0], validation[0]) is True
        assert spent() == 2
        return roster[0], 1

    replay = reuse_native_search(optimize)

    def run(cap, first_grade=False):
        callbacks = []
        count = 0

        def observe(prompt, case):
            nonlocal count
            count += 1
            callbacks.append((prompt, case))
            return first_grade if prompt == 'start' else True

        def spent():
            callbacks.append(count)
            return count

        result = replay('start', ('a',), (0,), (1,), observe, spent, paid_limit=cap, batched=False, seed=7)
        return result, callbacks

    assert run(8) == run(8) == (('a', 1), [0, ('start', 1), 1, ('a', 1), 2])
    assert run(9) == run(8)
    assert optimizations == [8, 9]
    with pytest.raises(ValueError, match='identical paid replies and spend'):
        run(8, first_grade=True)
