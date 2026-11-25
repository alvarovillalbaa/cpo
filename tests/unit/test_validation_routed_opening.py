from collections import Counter

import pytest

from benchmarks.validation_routed_opening import HALVING, play
from cpo import Observation, Row
from cpo.settled_episode import EpisodeCycle


@pytest.mark.parametrize(('grades', 'expected', 'routing_reads'),
                         (((False, True), 'uniform/8/18', 1),
                          ((True, False), 'uniform/8/18', 2),
                          ((True, True), HALVING, 2)))
def test_a_closed_qualification_gate_charges_only_the_validation_prefix(grades, expected, routing_reads):
    validation = tuple(Row(f'v{index}', 'validation') for index in range(2))
    qualification = tuple(Row(f'q{index}', 'qualification') for index in range(4))
    cycle = EpisodeCycle(('candidate',), validation, qualification)
    validation_calls, proof_calls = [], []

    def evaluate(prompt, row):
        assert prompt == 'base' and row in validation
        validation_calls.append(row)
        return Observation(grades[validation.index(row)], {})

    def qualify(prompt, row, repeat):
        assert prompt == 'base' and row in qualification and repeat == 0
        proof_calls.append(row)
        return True

    def probe(*args):
        pytest.fail('A routed episode must not ask for training')

    result = play('base', (), (cycle,), evaluate, probe=probe, qualify=qualify)
    assert result.schedule == expected
    assert result.prompt == 'base'
    assert validation_calls == list(validation[:routing_reads])
    assert result.cycles[0].search.evaluations == routing_reads
    assert result.evaluations == routing_reads + len(proof_calls)


def test_validation_prefix_reuses_a_funded_reply_and_charges_the_unused_reply():
    validation = tuple(Row(f'v{index}', 'validation') for index in range(6))
    qualification = tuple(Row(f'q{index}', 'qualification') for index in range(4))
    cycle = EpisodeCycle(tuple(f'candidate-{index}' for index in range(8)), validation, qualification)
    calls = Counter()

    def grade(prompt, row):
        calls[prompt, row.id] += 1
        assert calls[prompt, row.id] == 1
        return prompt == 'base' if row in validation else False

    result = play('base', (), (cycle,), lambda p, r: Observation(grade(p, r), {}),
                  probe=None, qualify=lambda p, r, _: grade(p, r))
    assert result.schedule == HALVING
    assert result.prompt == 'base'
    assert calls['base', 'v0'] == calls['base', 'v1'] == 1
    assert not any((prompt, 'v1') in calls for prompt in cycle.candidates)
    assert result.evaluations == len(calls)
