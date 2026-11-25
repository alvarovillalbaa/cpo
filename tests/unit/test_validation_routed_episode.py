from collections import Counter
from dataclasses import replace

import pytest

from cpo import Observation, Row
from cpo.full_roster_precheck.fixed_opening import run_fixed_opening_episode
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode
from cpo.settled_episode import EpisodeCycle


def layout(index, *, width=8, rows=6, critical=False):
    return EpisodeCycle(tuple(f'prompt-{index}-{i}' for i in range(width)),
                        tuple(Row(f'v-{index}-{i}', 'validation', critical=critical and i == 0)
                              for i in range(rows)),
                        tuple(Row(f'q-{index}-{i}', 'qualification') for i in range(4)), index)


@pytest.mark.parametrize('cycle', (layout(0, width=0), layout(0, rows=1), layout(0, critical=True)))
def test_unroutable_openings_follow_the_fixed_uniform_route(cycle):
    def play(runner, **kwargs):
        ledger = []

        def evaluate(prompt, row):
            ledger.append(('validation', prompt, row.id))
            return Observation(prompt != 'start', {})

        def qualify(prompt, row, repeat):
            ledger.append(('qualification', prompt, row.id))
            return prompt != 'start'

        return runner('start', iter((cycle,)), evaluate, qualify=qualify, **kwargs), ledger

    assert play(run_validation_routed_episode) == play(run_fixed_opening_episode, schedule='uniform/8/18')


@pytest.mark.parametrize('invalid', ('no-cycles', 'row', 'prompt', 'validation', 'qualification', 'roster'))
def test_validates_all_cycles_before_charging_a_routing_reply(invalid):
    first, second = layout(0), layout(1)
    cycles = {
        'no-cycles': (),
        'row': (first, replace(second, qualification=first.qualification)),
        'prompt': (first, replace(second, candidates=('start',))),
        'validation': (first, replace(second, validation=())),
        'qualification': (first, replace(second, qualification=())),
        'roster': (first, replace(second, candidates=(*second.candidates, 'extra'))),
    }[invalid]

    def unexpected(*args):
        pytest.fail('A callback ran before the complete layout was validated')

    with pytest.raises(ValueError):
        run_validation_routed_episode('start', iter(cycles), unexpected, qualify=unexpected)


def test_one_miss_reuses_a_grade_and_still_respects_a_critical_qualification_loss():
    cycle = layout(0)
    protected, *remaining = cycle.qualification
    cycle = replace(cycle, qualification=(replace(protected, critical=True), *remaining))
    seen = Counter()

    def grade(role, prompt, row):
        seen[role, prompt, row.id] += 1
        assert seen[role, prompt, row.id] == 1
        if role == 'qualification':
            return (prompt == 'start') == row.critical
        return prompt != 'start'

    result = run_validation_routed_episode('start', (cycle,),
        lambda prompt, row: Observation(grade('validation', prompt, row), {}),
        qualify=lambda prompt, row, repeat: grade('qualification', prompt, row))
    assert next(iter(seen)) == ('validation', 'start', 'v-0-0')
    assert result.schedule == 'uniform/8/18'
    assert result.cycles[0].search.finalist is not None
    assert result.cycles[0].qualification.status == 'rejected'
    assert result.prompt == 'start'
    assert result.training_evaluations == 0
    assert result.evaluations == sum(seen.values())
