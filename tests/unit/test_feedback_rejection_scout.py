import pytest

from benchmarks import feedback_rejection_scout as study
from cpo import Observation, Row
from cpo.feedback_episode import _RETAIN, run_feedback_episode
from cpo.settled_episode import EpisodeCycle


def test_scout_searches_only_the_cycle_that_feedback_would_skip():
    training = (Row('train-0', 'training'), Row('train-1', 'training'))
    cycles = tuple(EpisodeCycle(
        (candidate,), tuple(Row(f'v-{cycle}-{row}', 'validation') for row in range(3)),
        tuple(Row(f'q-{cycle}-{row}', 'qualification') for row in range(4)),
    ) for cycle, candidate in enumerate(('rejected', 'repair')))

    def episode():
        reads = []

        def evaluate(prompt, row):
            reads.append((prompt, row.id))
            return Observation(prompt != 'base', {})

        def qualify(prompt, row, repeat):
            assert repeat == 0
            return prompt == 'repair' or (prompt == 'base' and not row.id.endswith('-0'))

        result = run_feedback_episode('base', training, cycles, evaluate,
                                      probe=lambda prompt, row: True, qualify=qualify)
        return result, reads

    original, original_reads = episode()
    assert original.cycle_schedules[-1] == _RETAIN
    assert original.prompt == 'base'
    with study.use_scout():
        result, paid = episode()
    assert result.cycles[0] == original.cycles[0]
    assert result.cycle_schedules[-1] == study.SCOUT
    assert result.prompt == 'repair'
    assert paid == [*original_reads, ('base', 'v-1-0'), ('repair', 'v-1-0')]
    assert episode() == (original, original_reads)


@pytest.mark.parametrize('critical', (False, True))
def test_scout_respects_the_first_four_slots_and_a_late_critical_row(critical):
    roster = ('a', 'b', 'c', 'd', 'unfunded')
    validation = (Row('0', 'validation'), Row('1', 'validation', critical=critical))
    qualification = tuple(Row(str(n), 'qualification') for n in range(2, 6))
    seen = []

    def evaluate(prompt, row):
        seen.append((prompt, row.id))
        return Observation(prompt == 'unfunded', {})

    result = study.scout_cycle('base', roster, validation, qualification, evaluate, metric_limit=19,
                               qualify=lambda prompt, row, repeat: False, seed=0)
    assert result.search.finalist is None
    assert result.prompt == 'base'
    assert seen == ([] if critical else [(prompt, '0') for prompt in ('base', *roster[:4])])
    assert result.search.evaluations + result.qualification_evaluations == (0 if critical else 6)


def test_first_miss_reuses_the_paid_incumbent_grade_and_preserves_qualification():
    validation = tuple(Row(str(n), 'validation') for n in range(3))
    qualification = tuple(Row(str(n), 'qualification') for n in range(3, 7))
    paid = []

    def evaluate(prompt, row):
        paid.append((prompt, row.id))
        return Observation(prompt != 'base' or row.id == '0', {})

    result = study.scout_cycle('base', ('repair',), validation, qualification, evaluate, depth=2,
                               metric_limit=3, qualify=lambda prompt, row, repeat: prompt != 'base', seed=0)
    assert result.prompt == 'repair'
    assert paid == [('base', '0'), ('base', '1'), ('repair', '1')]
    assert len(paid) == result.search.evaluations
