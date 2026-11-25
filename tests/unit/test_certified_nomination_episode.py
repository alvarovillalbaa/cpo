from dataclasses import replace

import pytest

from cpo import Observation, Row
from cpo.full_roster_precheck.certified_nomination import run_certified_nomination_episode
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode
from cpo.settled_episode import EpisodeCycle


def cycle(index, *, width=2, depth=6, critical=False):
    return EpisodeCycle(tuple(f'candidate-{index}-{i}' for i in range(width)),
                        tuple(Row(f'v-{index}-{i}', 'validation', critical=critical and i == 0)
                              for i in range(depth)),
                        tuple(Row(f'q-{index}-{i}', 'qualification') for i in range(4)), index)


def play(runner, cycles, grade, **kwargs):
    ledger = []

    def record(role, prompt, row):
        key = role, prompt, row.id
        assert key not in ledger
        ledger.append(key)
        return grade(role, prompt, row)

    def qualify(prompt, row, repeat):
        assert repeat == 0
        return record('qualification', prompt, row)

    result = runner('base', iter(cycles), lambda p, r: Observation(record('validation', p, r), {}),
                    qualify=qualify, **kwargs)
    assert result.evaluations == len(ledger)
    assert all(step.search.evaluations <= 19 and step.qualification_evaluations <= 8 for step in result.cycles)
    return result, ledger


@pytest.mark.parametrize('first', (cycle(0, width=0), cycle(0, width=8), cycle(0, depth=1), cycle(0, critical=True)))
def test_other_screens_preserve_every_reply(first):
    def grade(role, prompt, row):
        return prompt != 'base'

    assert play(run_certified_nomination_episode, [first], grade) == play(run_validation_routed_episode, [first], grade)


@pytest.mark.parametrize('rates', (True, False))
def test_protected_qualification_still_rejects_and_advances_the_feedback_schedule(rates):
    first, later = cycle(0), cycle(1)
    first = replace(first, qualification=(replace(first.qualification[0], critical=True), *first.qualification[1:]))

    def grade(role, prompt, row):
        if role == 'qualification' and row.critical:
            return prompt == 'base'
        return prompt in (first.candidates[0], later.candidates[0])

    actual, ledger = play(run_certified_nomination_episode, [first, later], grade, use_validation_rates=rates)
    expected, baseline = play(run_validation_routed_episode, [first, later], grade)
    assert actual.cycle_schedules == expected.cycle_schedules == ('uniform/8/18', 'fitted-opening-repair')
    assert [step.search.finalist for step in actual.cycles] == [step.search.finalist for step in expected.cycles]
    assert actual.cycles[0].qualification.status == 'rejected'
    assert actual.prompt == expected.prompt == later.candidates[0]
    assert ledger[0] == ('validation', 'base', first.validation[0].id)
    assert len(ledger) < len(baseline)


def test_entire_layout_is_validated_before_the_first_probe():
    first, later = cycle(0), cycle(1)
    later = replace(later, qualification=first.qualification)

    def unexpected(*args):
        pytest.fail('An invalid later cycle must fail before the opening')

    with pytest.raises(ValueError, match='disjoint'):
        run_certified_nomination_episode('base', [first, later], unexpected, qualify=unexpected)
