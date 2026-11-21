from bisect import bisect_right
from random import Random

import pytest

from benchmarks import recorded_certificate_cost_frontier as study


@pytest.mark.parametrize('mode', study.MODES)
def test_paid_round_boundaries_match_direct_replay_at_every_integer_cap(mode):
    rng = Random(6318)
    cells = {str(prompt): tuple((int(rng.random() < 0.2 + prompt / 20), None, False) for _ in range(28))
             for prompt in range(9)}
    cells['0'] = tuple((0, None, False) for _ in range(28))
    cohorts = (list(range(10)), list(range(10, 16)), list(range(16, 20)), list(range(20, 28)))
    arguments = (cells, '0', tuple(str(prompt) for prompt in range(1, 9)), cohorts, 43101)
    paths = study.budget_paths(arguments, mode, 6, 180)
    cuts = tuple(paths)
    assert len(cuts) > 2
    for cap in range(6, 181):
        assert paths[cuts[bisect_right(cuts, cap) - 1]] == study.run(arguments, mode, cap)
