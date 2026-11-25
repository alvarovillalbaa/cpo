from hashlib import sha256

import pytest

from benchmarks import full_roster_precheck_prospective as study
from cpo import Observation, Row
from cpo._contract import digest
from cpo.feedback_episode import run_feedback_episode
from cpo.full_roster_precheck import run_full_roster_feedback_episode
from cpo.settled_episode import EpisodeCycle


TRAINING = (Row('t0', 'training'), Row('t1', 'training'))


def scenario(width, critical=False, offset=0):
    return EpisodeCycle(tuple(f'p-{offset}-{candidate}' for candidate in range(width)),
                        tuple(Row(f'v-{offset}-{row}', 'validation', critical=critical and row == 5)
                              for row in range(6)),
                        tuple(Row(f'q-{offset}-{row}', 'qualification') for row in range(4)), offset)


@pytest.mark.parametrize('training_passes', (0, 1, 2))
@pytest.mark.parametrize(('width', 'critical'), ((2, False), (8, True), (8, False)))
def test_opt_in_preserves_decisions_and_reconciles_actual_callbacks(training_passes, width, critical):
    cycles = tuple(scenario(width, critical, i) for i in range(3))

    def play(runner):
        paid = []

        def grade(prompt, row, repeat=0):
            paid.append((prompt, row.id, repeat))
            if row.family == 'training':
                return int(row.id[-1]) < training_passes
            return sha256(f'{prompt}/{row.id}'.encode()).digest()[0] < 128

        result = runner('base', iter(TRAINING), iter(cycles), lambda prompt, row: Observation(grade(prompt, row), {}),
                        probe=grade, qualify=grade)
        assert result.evaluations == len(paid) == len(set(paid))
        return result, paid

    baseline, original_paid = play(run_feedback_episode)
    candidate, candidate_paid = play(run_full_roster_feedback_episode)
    assert (candidate.prompt, candidate.schedule, candidate.cycle_schedules) == (
        baseline.prompt, baseline.schedule, baseline.cycle_schedules,
    )
    assert [(step.search.finalist, step.prompt) for step in candidate.cycles] == [
        (step.search.finalist, step.prompt) for step in baseline.cycles
    ]
    if width == 2 or critical:
        assert candidate == baseline
        assert candidate_paid == original_paid


def test_invalid_episode_buys_no_replies():
    same = scenario(8)

    def unexpected(*_):
        pytest.fail('Callback before verifying disjoint roles and rosters')

    with pytest.raises(ValueError, match='disjoint'):
        run_full_roster_feedback_episode('base', TRAINING, (same, same), unexpected,
                                         probe=unexpected, qualify=unexpected)


def test_a_paired_critical_qualification_loss_still_blocks_the_promotion():
    cycle = scenario(8)
    proof = (Row('protected', 'qualification', critical=True), *cycle.qualification[1:])
    result = run_full_roster_feedback_episode(
        'base', TRAINING, (EpisodeCycle(cycle.candidates, cycle.validation, proof),),
        lambda prompt, _: Observation(prompt != 'base', {}), probe=lambda _, row: row.id == 't0',
        qualify=lambda prompt, row, _: (prompt == 'base') == row.critical,
    )
    assert result.cycles[0].search.finalist is not None
    assert result.cycles[0].qualification.status == 'rejected'
    assert result.prompt == 'base'


def test_rehearsal_adds_one_arm_and_replays_its_gate(tmp_path):
    _, plan = study.prepare()
    _, parent = study.parent.prepare()
    assert plan['parentPlanSha256'] == digest(parent)
    assert plan['arms'] == (*parent['arms'], study.CANDIDATE)
    assert sum(plan['physicalLimitsByRole'].values()) == plan['requestCeiling'] == 2151
    assert plan['datasetSha256'] == parent['datasetSha256']
    first = tmp_path / 'fixture'
    result, verdict = study.run_fixture(digest(plan), first)
    assert study.replay(first, tmp_path / 'replay') == (result, verdict)
    assert verdict['sameFeedbackChoices'] and verdict['sameFeedbackHoldoutGrades']
    assert verdict['searchSavingsAgainstFeedback'] == {'logicalSearchUses': 7, 'attributedSearchRequests': 7}
    assert verdict['feedbackGatePassed'] and not verdict['fullDevelopmentGatePassed']
