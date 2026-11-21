"""T2 checks for overlapping paid lookups in the sealed comparison."""

from itertools import product
from random import Random

import pytest

from benchmarks import pool, witness_halving_physical_limits as limits
from cpo.halving import HalvingSearch


def test_sealed_physical_limits_reduce_only_the_transport_ceiling():
    outcome = limits.prepare()
    assert outcome['evaluationComponentsPerTask'] == {'GEPA': 200, 'Halving': 56, 'witness': 120, 'fallback': 16}
    assert outcome['maxRequestsByRole'] == {'reflection': 12, 'evaluation': 1176, 'admission': 768, 'qualification': 756}
    assert outcome['maxRequests'] == 2712


def test_halving_pair_adds_at_most_fourteen_grades_beyond_the_native_seed():
    prompts, cases = ('start', 'rewrite', 'repair'), tuple(range(5))
    roster = tuple(product(prompts, cases))
    seed = {('start', case) for case in cases}
    maximum = 0
    for bits in product((False, True), repeat=len(roster)):
        table = dict(zip(roster, bits, strict=True))
        scheduled, certified = set(), set()
        for cap in (8, 12):
            def observe(prompt, case):
                scheduled.add((prompt, case))
                return table[prompt, case]

            expected = pool.successive_halving(prompts, cases, observe, cap)
            search = HalvingSearch(metric_limit=cap)
            assert search.select(prompts, cases, lambda p, r: table[p, r], logical_limit=cap) == expected
            certified.update(search.observations)
        assert certified <= scheduled
        maximum = max(maximum, len(scheduled - seed))
    assert maximum <= 14


def test_native_uses_the_same_seed_anchors_in_each_pinned_cycle():
    pytest.importorskip('gepa')
    original = limits.futility.parent.original
    anchors = tuple(f'anchor-{index}' for index in range(original.GEPA_ANCHORS))
    shared = {('start', case) for case in anchors}
    for trial in range(8):
        distinct = set()
        for arm_index, arm in enumerate(original.GEPA):
            for cycle in range(original.CYCLES):
                paid = []
                rng = Random(f'{trial}:{arm}:{cycle}')

                def observe(prompt, case):
                    paid.append((prompt, case))
                    return bool(rng.getrandbits(1))

                train = tuple(f'train-{cycle}-{i}' for i in range(original.TRAIN_ROWS))
                alternatives = (f'rewrite-{cycle}', f'repair-{cycle}')
                original.native('start', alternatives, train, anchors, observe, batched=bool(arm_index),
                                cap=original.CAPS[arm], seed=original.SEED + cycle)
                assert set(paid[:len(anchors)]) == shared
                assert len(set(paid)) <= original.CAPS[arm]
                distinct.update(paid)
        assert len(distinct) <= 200
