from itertools import product

import pytest

from benchmarks.first_gain_validation_width import run, screen
from cpo import Observation, Row
from cpo.settled_episode import EpisodeCycle


@pytest.mark.parametrize('width', (1, 2, 3))
def test_short_panel_certifies_on_every_boolean_board(width):
    rows = tuple(Row(f'v{index}', 'validation') for index in range(6))
    prompts = ('base', 'a', 'b')
    for board in product((False, True), repeat=width * len(prompts)):
        seen = set()

        def evaluate(prompt, row):
            index = rows.index(row)
            assert index < width
            key = prompt, row.id
            assert key not in seen
            seen.add(key)
            return Observation(board[prompts.index(prompt) * width + index], {})

        result, _ = screen(width, prompts[0], prompts[1:], rows, evaluate, 19,
                           prepaid={row.id for row in rows[:2]}, read_limit=18)
        scores = {prompt: sum(board[index * width:(index + 1) * width]) for index, prompt in enumerate(prompts)}
        if result.finalist is None:
            assert scores['base'] == max(scores.values())
        else:
            assert scores[result.finalist] > scores['base']
        assert result.evaluations == len(seen)


def test_short_panel_preserves_opening_accounting_and_independent_qualification():
    cases = tuple(Row(f'v{index}', 'validation') for index in range(6))
    qualification = tuple(Row(f'q{index}', 'qualification') for index in range(4))
    cycle = EpisodeCycle(('a', 'b'), cases, qualification, 0)
    paid = set()

    def evaluate(prompt, row):
        assert (prompt, row.id) not in paid
        paid.add((prompt, row.id))
        return Observation(prompt == 'a', {})

    result = run(1, 'base', (), (cycle,), evaluate, probe=None,
                 qualify=lambda prompt, row, repeat: row.id != 'q0')
    assert result.cycles[0].search.finalist == 'a'
    assert result.cycles[0].qualification.status == 'rejected'
    assert result.prompt == 'base'
    assert {row for _, row in paid} <= {'v0', 'v1'}
    assert result.cycles[0].search.evaluations == len(paid)
