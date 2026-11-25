from random import Random

from benchmarks import certified_nomination_gepa_sweep as sweep


def test_representatives_cover_the_skipped_native_caps():
    roster = ('left', 'right')
    start = sweep.transfer.donor.START
    windows = [(roster, tuple(range(12)), tuple(range(12, 18)), tuple(range(18, 22)))]
    menu = sweep.sweep_settings({})
    for seed in (11, 19, 25):
        rng = Random(seed)
        matrix = {prompt: ''.join(str(rng.randrange(2)) for _ in range(22)) for prompt in (start, *roster)}
        for mode in ('sequential', 'batched'):
            for rows in range(1, 7):
                for batch in (1, 2):
                    spec = {'mode': mode, 'validationRows': rows, 'batch': batch}
                    paths = {item['searchCap']: sweep.play({'controlSettings': menu}, matrix, windows, seed, arm)
                             for arm, item in menu.items() if all(item[key] == value for key, value in spec.items())}
                    for cap in range(rows, 33):
                        representative = max(value for value in paths if value <= cap)
                        trial = {'controlSettings': {'native': {**spec, 'searchCap': cap}}}
                        actual = sweep.play(trial, matrix, windows, seed, 'native')
                        assert actual == paths[representative]


def test_control_deduplication_preserves_all_lookup_and_historical_cost_points():
    totals = {'a': {'paidLookups': 4, sweep.math.PRICE: 100},
              'b': {'paidLookups': 4, sweep.math.PRICE: 100},
              'c': {'paidLookups': 4, sweep.math.PRICE: 110}}
    vectors = dict.fromkeys(totals, [1, 0])
    assert sweep.distinct_controls(('c', 'b', 'a'), [(totals, vectors)]) == ('a',)
    assert sweep.distinct_controls(('c', 'b', 'a'), [(totals, vectors)], priced=True) == ('a', 'c')
