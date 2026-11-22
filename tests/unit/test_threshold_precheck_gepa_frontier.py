import pytest

from benchmarks import threshold_precheck_gepa_frontier as frontier


@pytest.mark.parametrize(('incumbent', 'winner', 'search_lookups', 'proof_lookups'), [
    ('0111', 'start', 0, 4),
    ('0001', 'nominee', 2, 7),
])
def test_gepa_uses_the_same_threshold_before_any_native_search(
    monkeypatch, incumbent, winner, search_lookups, proof_lookups,
):
    mode = frontier.cost.MODES[0]
    matrix = {
        'start': '000' + incumbent + '0',
        'nominee': '01111111',
    }
    cells = {name: tuple((int(passed), None, False) for passed in row) for name, row in matrix.items()}
    called = []

    def native(start, roster, train, validation, observe, spent, *, paid_limit, batched, seed):
        assert (start, roster, train, validation, paid_limit, batched, seed) == (
            'start', ('nominee',), (0,), (1, 2), 2, False, 7,
        )
        called.append(True)
        assert spent() == 0
        assert observe('start', 1) is False
        assert observe('nominee', 1) is True
        assert observe('nominee', 1) is True
        assert spent() == 2
        return 'nominee', 1

    monkeypatch.setattr(frontier.cost.adapter.math.gepa, 'optimize_by_paid_reads', native)
    args = cells, 'start', ('nominee',), ((0,), (1, 2), (3, 4, 5, 6), (7,)), 7
    point, trace, grades = frontier.gepa_threshold(args, mode, 2)
    assert bool(called) == bool(search_lookups)
    assert trace[3] == winner
    assert grades == (int(winner == 'nominee'),)
    assert point['searchLookups'] == search_lookups
    assert point['qualificationLookups'] == proof_lookups
    assert point['paidLookups'] == search_lookups + proof_lookups
