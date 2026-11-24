from dataclasses import replace

import pytest

from cpo import Observation, Row
from cpo.feedback_episode import run_feedback_episode
from cpo.settled_episode import EpisodeCycle


def panel(role, cycle, count):
    return tuple(Row(f'{role}-{cycle}-{index}', f'{role}-{cycle}') for index in range(count))


def stages():
    return tuple(EpisodeCycle((f'candidate-{cycle}',), panel('validation', cycle, 6),
                              panel('qualification', cycle, 4), cycle)
                 for cycle in range(3))


@pytest.mark.parametrize(('grades', 'opening', 'follow_up'), (
    ((False, False), 'fitted-opening-repair', 'successive-halving/8/14'),
    ((False, True), 'uniform/8/18', 'fitted-opening-repair'),
    ((True, False), 'uniform/8/18', 'fitted-opening-repair'),
    ((True, True), 'successive-halving/4/6', 'retain-start'),
))
def test_rejected_finalist_switches_only_the_next_cycle(grades, opening, follow_up):
    training, cycles = panel('training', 0, 2), stages()
    paid = []

    def probe(prompt, row):
        assert prompt == 'initial'
        paid.append(('training', prompt, row.id))
        return grades[training.index(row)]

    def evaluate(prompt, row):
        paid.append(('validation', prompt, row.id))
        return Observation(prompt == f'candidate-{row.family[-1]}', {})

    def qualify(prompt, row, repeat):
        assert repeat == 0
        paid.append(('qualification', prompt, row.id))
        return row.family != 'qualification-0' and prompt == f'candidate-{row.family[-1]}'

    result = run_feedback_episode('initial', training, cycles, evaluate, probe=probe, qualify=qualify)
    assert result.schedule == opening
    assert result.cycle_schedules == (opening, follow_up, opening)
    assert result.cycles[0].search.finalist == 'candidate-0'
    assert result.cycles[0].qualification.status == 'rejected'
    assert result.cycles[0].prompt == 'initial'
    assert result.prompt == 'candidate-2'
    assert result.training_evaluations == 2
    assert result.evaluations == len(paid) == len(set(paid))
    third_probe = cycles[2].qualification[0].id
    if follow_up == 'retain-start':
        assert result.cycles[1].qualification is None
        assert result.cycles[1].prompt == 'initial'
        assert not any(row in {r.id for r in (*cycles[1].validation, *cycles[1].qualification)}
                       for _, _, row in paid)
        assert ('qualification', 'initial', third_probe) in paid
    else:
        assert result.cycles[1].promoted
        assert ('qualification', 'candidate-1', third_probe) in paid


@pytest.mark.parametrize('all_pass', (False, True))
def test_no_finalist_keeps_the_opening_schedule(all_pass):
    def probe(prompt, row):
        return row.id.endswith('-1')

    observed = run_feedback_episode(
        'initial', panel('training', 0, 2), stages(), lambda prompt, row: Observation(False, {}),
        probe=probe, qualify=lambda prompt, row, repeat: all_pass,
    )
    assert observed.cycle_schedules == ('uniform/8/18',) * 3
    assert [cycle.search.finalist for cycle in observed.cycles] == [None] * 3
    assert all(bool(cycle.search.evaluations) != all_pass for cycle in observed.cycles)


def test_wrong_future_role_fails_before_a_paid_callback():
    training, cycles = panel('training', 0, 2), stages()
    invalid = (*cycles[:-1], replace(cycles[-1], validation=training))

    def charged(*args):
        pytest.fail(f'Invalid role layout called the evaluator with {args}')

    with pytest.raises(ValueError, match='disjoint row IDs'):
        run_feedback_episode('initial', training, invalid, charged, probe=charged, qualify=charged)
