"""T2 mock validation and qualification grades."""

from functools import partial

import pytest

from benchmarks.paid_prefix_archive_routing import PREFIX, PROBE, STATIC, profiled_cycle, transfer
from cpo import Observation, Row


@pytest.mark.parametrize('mode,expected_state', [(STATIC, 'open'), (PREFIX, '2'), (PROBE, '2/1')])
def test_router_observes_only_paid_replies_before_choosing(mode, expected_state):
    validation = tuple(Row(f'v{i}', 'validation') for i in range(6))
    qualification = tuple(Row(f'q{i}', 'qualification') for i in range(4))
    readings = []

    def evaluate(prompt, row):
        key = prompt, row.id
        assert key not in readings
        readings.append(key)
        return Observation(True, {})

    def qualify(prompt, row, _):
        readings.append((prompt, row.id))
        return prompt == 'rival' or row.id == 'q0'

    def choose(state):
        assert state == expected_state
        want = [('base', 'q0'), ('base', 'q1')]
        if mode == PROBE:
            want.append(('base', 'v0'))
        assert readings == want
        return 'certified-wide'

    decision = profiled_cycle('base', ('rival',), validation, qualification, evaluate, metric_limit=19,
                              qualify=qualify, minimum_gain=1, seed=17, model=mode, choose=choose)
    assert decision.promoted
    assert decision.search.evaluations == sum(case.startswith('v') for _, case in readings)


def test_retain_counts_the_probe_and_closed_precheck_never_opens_a_route():
    validation = (Row('validation', 'search'),)
    qualification = (Row('qualification', 'qualification'),)
    calls = []

    def evaluate(prompt, row):
        calls.append((prompt, row.id))
        return Observation(False, {})

    def choose(state):
        assert state == '1/0'
        return transfer.RETAIN

    run = partial(profiled_cycle, metric_limit=19, minimum_gain=1, seed=17, model=PROBE, choose=choose)
    closed = run('base', ('rival',), validation, qualification, evaluate, qualify=lambda *_: True)
    assert not calls and closed.search.evaluations == 0
    open_ = run('base', ('rival',), validation, qualification, evaluate, qualify=lambda *_: False)
    assert calls == [('base', 'validation')]
    assert open_.prompt == 'base' and open_.search.evaluations == 1
