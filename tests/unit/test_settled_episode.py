from dataclasses import replace

import pytest

from cpo import Observation, Row
from cpo.settled_episode import EpisodeCycle, run_settled_episode


def panel(name, size):
    return tuple(Row(f'{name}-{index}', name) for index in range(size))


def cycles():
    return tuple(EpisodeCycle((f'proposal-{index}',), panel(f'validation-{index}', 6),
                              panel(f'qualification-{index}', 4), index)
                 for index in range(3))


@pytest.mark.parametrize(('grades', 'schedule'), (
    ((False, False), 'fitted-opening-repair'),
    ((False, True), 'uniform/8/18'),
    ((True, False), 'uniform/8/18'),
    ((True, True), 'successive-halving/4/6'),
))
def test_chosen_schedule_carries_only_qualified_prompts_and_counts_callbacks(grades, schedule):
    training, stages = panel('training', 2), cycles()
    paid = []

    def probe(prompt, row):
        assert prompt == 'initial'
        assert row == training[len(paid)]
        paid.append(('training', prompt, row.id))
        return grades[len(paid) - 1]

    def evaluate(prompt, row):
        paid.append(('validation', prompt, row.id))
        return Observation(prompt == f'proposal-{row.family[-1]}', {})

    def qualify(prompt, row, repeat):
        assert repeat == 0
        paid.append(('qualification', prompt, row.id))
        return row.family != 'qualification-1' and prompt == f'proposal-{row.family[-1]}'

    result = run_settled_episode('initial', training, stages, evaluate, probe=probe, qualify=qualify)

    assert result.schedule == schedule
    assert [cycle.search.finalist for cycle in result.cycles] == ['proposal-0', 'proposal-1', 'proposal-2']
    assert [cycle.prompt for cycle in result.cycles] == ['proposal-0', 'proposal-0', 'proposal-2']
    assert result.prompt == 'proposal-2'
    assert result.training_evaluations == 2
    assert result.evaluations == len(paid) == len(set(paid))
    assert ('qualification', 'proposal-0', 'qualification-2-0') in paid
    assert ('qualification', 'proposal-1', 'qualification-2-0') not in paid


@pytest.mark.parametrize('bad_stage', ('reused-row', 'reused-prompt', 'missing-qualification'))
def test_invalid_later_cycle_fails_before_any_probe(bad_stage):
    training, stages = panel('training', 2), cycles()
    last = stages[-1]
    invalid = {
        'reused-row': replace(last, validation=training),
        'reused-prompt': replace(last, candidates=stages[0].candidates),
        'missing-qualification': replace(last, qualification=()),
    }

    def read(*args):
        pytest.fail(f'Invalid input must fail before issuing a callback {args!r}')

    with pytest.raises(ValueError):
        run_settled_episode('initial', training, (*stages[:-1], invalid[bad_stage]), read,
                            probe=read, qualify=read)
