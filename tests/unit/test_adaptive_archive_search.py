"""T2 scripted grades for the paid search routing feature."""

from functools import partial

import pytest

from benchmarks.adaptive_archive_search import cycle, limited, retain
from benchmarks.continuous_search_controls import HALVING, screen
from cpo.optimizer import Observation, Row
from cpo.two_sided_certificate_cycle import _run


@pytest.mark.parametrize('first_passed', [False, True])
def test_chosen_screen_matches_direct_execution_without_extra_qualification_reads(first_passed):
    qualification = (Row('proof-1', 'qualification'), Row('proof-2', 'qualification'))
    validation = (Row('val', 'validation'),)
    halving = partial(limited, partial(screen, mode=HALVING, width=4), 3)
    actions = (halving, retain)

    def run(runner):
        ledger = []

        def qualify(prompt, row, repeat):
            ledger.append(('proof', prompt, row.id, repeat))
            return prompt != 'base' or (row.id == 'proof-1' and first_passed)

        def evaluate(prompt, row):
            ledger.append(('search', prompt, row.id))
            return Observation(prompt != 'base', {})

        result = runner('base', ('a', 'b'), validation, qualification, evaluate, metric_limit=9,
                        qualify=qualify, minimum_gain=1, seed=42)
        return result, ledger

    routed = run(partial(cycle, actions=actions))
    direct = run(partial(_run, screen=actions[int(first_passed)]))
    assert routed == direct
    result, ledger = routed
    assert ledger[0] == ('proof', 'base', 'proof-1', 0)
    assert ledger.count(ledger[0]) == 1
    assert result.prompt == ('base' if first_passed else 'a')
