from functools import partial
from itertools import product

import pytest

from benchmarks import promptolution_settled_episode_read_order as order
from benchmarks import two_challenger_uniform_order as uniform
from cpo import Observation, Row


@pytest.mark.parametrize(('original', 'variant', 'caps'), (
    (order._QUOTED, partial(order.screen, order._QUOTED), (3, 5, 7, 9)),
    (order._BOUNDED, partial(order.screen, order._BOUNDED), (3, 5, 7, 9)),
    (uniform._ORIGINAL, uniform.screen, (9, 12)),
))
def test_every_four_row_boolean_panel_preserves_nominee_and_proof_counts(original, variant, caps):
    prompts = ('base', 'first', 'second')
    rows = tuple(Row(str(i), 'validation') for i in range(4))
    for grades in product((False, True), repeat=len(prompts) * len(rows)):
        table = dict(zip(product(prompts, rows), grades, strict=True))
        for cap in caps:
            results = []
            for screen in (original, variant):
                observed = set()

                def evaluate(prompt, row):
                    key = prompt, row
                    assert key not in observed
                    observed.add(key)
                    return Observation(table[key], {})

                result, counts = screen(prompts[0], prompts[1:], rows, evaluate, cap)
                assert result.evaluations == len(observed) <= cap
                results.append((result.prompt, result.finalist, counts))
            assert results[0] == results[1]


@pytest.mark.parametrize(('candidates', 'critical'), ((('a', 'b'), True), (('a', 'b', 'c'), False)))
def test_unsupported_rosters_and_critical_panels_use_the_original_path(candidates, critical):
    rows = (Row('first', 'validation'), Row('second', 'validation', critical=critical))
    original = object()

    def fallback(incumbent, seen, panel, evaluate, cap):
        assert (incumbent, seen, panel, evaluate, cap) == ('base', candidates, rows, None, 9)
        return original

    assert order.screen(fallback, 'base', candidates, rows, None, 9) is original
