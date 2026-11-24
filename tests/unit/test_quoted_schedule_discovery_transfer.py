"""T2 checks that a selected quoted action keeps its roster and cap."""

from benchmarks.quoted_schedule_discovery_transfer import limited_quote
from cpo import Observation, Row


def test_quoted_action_preserves_its_narrow_roster_and_shorter_budget():
    rows = tuple(Row(str(i), 'validation') for i in range(4))
    reads = []

    def evaluate(prompt, row):
        reads.append((prompt, row))
        return Observation(prompt != 'base', {})

    winner, counts = limited_quote('base', ('a', 'b', 'outsider'), rows, evaluate, 50,
                                   mode='successive-halving', width=2, limit=5)
    assert winner.finalist == 'a'
    assert counts == ((0, 2), (2, 2))
    assert {prompt for prompt, _ in reads} <= {'base', 'a', 'b'}
    assert {row for _, row in reads} == set(rows[:2])
    assert len(reads) == winner.evaluations <= 5
