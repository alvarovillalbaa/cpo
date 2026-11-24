from functools import partial
from itertools import product

import pytest

from cpo import Observation, Row
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.quoted_shared_validation_cycle import _screen as quoted_screen
from cpo.second_case_qualification import GUARDS, NO_LOSS, TWO_GAIN, run_second_case_qualification_cycle
from cpo.switch_validation_case import screen


ROSTER = tuple('abcdefgh')
VALIDATION = tuple(Row(f'v{index}', 'validation') for index in range(3))
QUALIFICATION = tuple(Row(f'q{index}', 'qualification') for index in range(4))
OPENING = partial(quoted_screen, halve=True)
SWITCH = partial(screen, initial_probes=2, unopened_first=True)


def run(policy, grades, validation, *, seed=0):
    reads = []
    cells = dict(zip(((prompt, row) for prompt in ('base', 'c') for row in QUALIFICATION), grades, strict=True))

    def qualify(prompt, row, repeat):
        assert any(row is original for original in QUALIFICATION)
        cell = prompt, row
        assert cell not in reads and repeat == 0
        reads.append(cell)
        return cells[cell]

    outcome = policy('base', ROSTER, VALIDATION, QUALIFICATION,
                     lambda prompt, row: Observation((prompt, row.id) in validation, {}),
                     metric_limit=9, qualify=qualify, seed=seed)
    assert len(reads) == outcome.qualification_evaluations <= 8
    assert [(prompt, row.id) for prompt, row in reads] == [
        (reply.prompt, reply.row_id) for reply in outcome.qualification.observations]
    return outcome, reads


@pytest.mark.parametrize('guard', GUARDS)
def test_each_independent_gate_matches_its_complete_panel_and_reuses_the_prefix(guard):
    baseline = partial(run_qualification_prefix_cycle, screens=(OPENING, SWITCH, SWITCH, SWITCH))
    guarded = partial(run_second_case_qualification_cycle, opening_screen=OPENING, switch_screen=SWITCH, guard=guard)
    validation = {('c', 'v1')}
    for suffix in product((False, True), repeat=7):
        grades = (True, *suffix)
        for seed in (0, 7):
            before, old_reads = run(baseline, grades, validation, seed=seed)
            after, reads = run(guarded, grades, validation, seed=seed)
            gains = [challenger - incumbent for incumbent, challenger in zip(grades[:4], grades[4:], strict=True)]
            expected = sum(gains) >= 2 if guard == TWO_GAIN else sum(gains) >= 1 and min(gains) >= 0
            assert after.prompt == ('c' if expected else 'base')
            assert before.search == after.search
            assert reads[:len(old_reads)] == old_reads
            if not before.promoted:
                assert after == before


@pytest.mark.parametrize('guard', GUARDS)
def test_opening_case_winner_uses_only_the_original_qualification(guard):
    baseline = partial(run_qualification_prefix_cycle, screens=(OPENING, SWITCH, SWITCH, SWITCH))
    guarded = partial(run_second_case_qualification_cycle, opening_screen=OPENING, switch_screen=SWITCH, guard=guard)
    validation = {('base', 'v1'), ('c', 'v0')}
    grades = (True, False, True, False, False, True, True, True)
    original = run(baseline, grades, validation)
    assert original[0].prompt == 'c'
    assert run(guarded, grades, validation) == original
