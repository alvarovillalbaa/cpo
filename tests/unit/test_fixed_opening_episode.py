from dataclasses import replace
from hashlib import sha256

import pytest

from cpo import Observation, Row
from cpo.full_roster_precheck import run_full_roster_feedback_episode
from cpo.full_roster_precheck.fixed_opening import FIXED_OPENING_SCHEDULES, run_fixed_opening_episode
from cpo.settled_episode import EpisodeCycle


TRAINING = (Row('training-0', 'training'), Row('training-1', 'training'))


def make_cycle(index, width=8, *, critical=False):
    return EpisodeCycle(
        tuple(f'prompt-{index}-{offset}' for offset in range(width)),
        tuple(Row(f'validation-{index}-{offset}', 'validation', critical=critical and offset == 0)
              for offset in range(6)),
        tuple(Row(f'qualification-{index}-{offset}', 'qualification') for offset in range(4)),
        index,
    )


@pytest.mark.parametrize(('passes', 'schedule'), tuple(enumerate(FIXED_OPENING_SCHEDULES)))
@pytest.mark.parametrize(('width', 'critical'), ((4, False), (8, True), (8, False)))
def test_fixed_schedule_reproduces_adaptive_feedback_without_the_probes(passes, schedule, width, critical):
    cycles = tuple(make_cycle(index, width, critical=critical) for index in range(3))

    def callbacks(ledger):
        def grade(prompt, row, repeat=0):
            ledger.append((prompt, row.id, repeat))
            if row.family == 'training':
                return int(row.id[-1]) < passes
            return sha256(f'{prompt}/{row.id}'.encode()).digest()[0] < 128

        return lambda prompt, row: Observation(grade(prompt, row), {}), grade

    original_ledger, ledger = [], []
    evaluate, grade = callbacks(original_ledger)
    original = run_full_roster_feedback_episode('base', iter(TRAINING), iter(cycles), evaluate,
                                               probe=grade, qualify=grade)
    evaluate, grade = callbacks(ledger)
    fixed = run_fixed_opening_episode('base', iter(cycles), evaluate, schedule=schedule, qualify=grade)
    assert fixed == replace(original, training_evaluations=0)
    assert ledger == original_ledger[original.training_evaluations:]
    assert fixed.evaluations == len(ledger) == len(set(ledger))


def test_critical_loss_rejects_then_the_halving_follow_up_skips_one_cycle():
    first, second, third = (make_cycle(index) for index in range(3))
    protected, *others = first.qualification
    first = replace(first, qualification=(replace(protected, critical=True), *others))
    seen = []

    def evaluate(prompt, row):
        seen.append(row.id)
        return Observation(prompt != 'base', {})

    def qualify(prompt, row, repeat):
        seen.append(row.id)
        return (prompt == 'base') == row.critical

    schedule = 'successive-halving/4/6'
    result = run_fixed_opening_episode('base', (first, second, third), evaluate, schedule=schedule, qualify=qualify)
    assert result.cycle_schedules == (schedule, 'retain-start', schedule)
    assert result.cycles[0].search.finalist is not None
    assert result.cycles[0].qualification.status == 'rejected'
    assert result.cycles[0].prompt == result.cycles[1].prompt == 'base'
    assert result.cycles[2].promoted and result.prompt == third.candidates[0]
    assert not any(row.id in seen for row in (*second.validation, *second.qualification))
    assert result.evaluations == len(seen)


@pytest.mark.parametrize('invalid', ('schedule', 'empty', 'row', 'prompt', 'validation', 'qualification', 'roster'))
def test_rejects_entire_invalid_episode_before_any_callback(invalid):
    first, second = make_cycle(0), make_cycle(1)
    cycles = {
        'schedule': (first,),
        'empty': (),
        'row': (first, replace(second, validation=first.validation)),
        'prompt': (first, replace(second, candidates=first.candidates)),
        'validation': (first, replace(second, validation=())),
        'qualification': (first, replace(second, qualification=second.qualification[:-1])),
        'roster': (first, replace(second, candidates=(*second.candidates, 'extra'))),
    }[invalid]
    schedule = 'unsupported' if invalid == 'schedule' else 'uniform/8/18'

    def unexpected(*_):
        pytest.fail('Evaluation started before the episode was validated')

    with pytest.raises(ValueError):
        run_fixed_opening_episode('base', cycles, unexpected, schedule=schedule, qualify=unexpected)
