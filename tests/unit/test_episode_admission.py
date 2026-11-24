from itertools import product

import pytest

from benchmarks.episode_admission_transfer import ADMIT, BOTH, BOUNDED, FAST_TWO, RETAIN, SCHEDULE, actions
from cpo.episode_admission import retain_after_training_prefix


@pytest.mark.parametrize('count', (1, 2, 3, 4))
def test_short_prefix_matches_complete_evidence_and_skips_only_unneeded_rows(count):
    for grades in product((False, True), repeat=count):
        rows = tuple(range(count))
        ledger = []

        def read(prompt, case):
            assert prompt == 'base'
            ledger.append(case)
            return grades[case]

        assert retain_after_training_prefix('base', rows, read, count=count) == all(grades)
        paid = grades.index(False) + 1 if False in grades else count
        assert ledger == list(rows[:paid])


@pytest.mark.parametrize('grades', tuple(product((False, True), repeat=2)))
def test_two_probe_controls_change_only_their_designated_branch(grades):
    plan = {'probeModes': {BOTH: (2, False)}, 'twoProbeActions': {'0': BOUNDED, '1': 'wider', '2': RETAIN},
            'prefixLengths': {FAST_TWO: 2}}
    stage = (1, ('candidate',), ((0, 1), (2,), (3,), (4,)))
    arms = actions(plan, {'base': grades}, (stage,), 'base')
    state = sum(grades)
    assert arms[BOTH][0] == plan['twoProbeActions'][str(state)]
    assert arms[SCHEDULE][0] == ('wider' if state == 1 else BOUNDED)
    assert arms[ADMIT][0] == arms[FAST_TWO][0] == (RETAIN if state == 2 else BOUNDED)
    assert len(arms[ADMIT][1]) == 2
    assert len(arms[FAST_TWO][1]) == (2 if grades[0] else 1)


def test_prefix_rejects_an_invalid_count_or_nonboolean_reply():
    with pytest.raises(ValueError, match='fit the available training rows'):
        retain_after_training_prefix('base', (0,), None, count=2)
    with pytest.raises(ValueError, match='exact boolean'):
        retain_after_training_prefix('base', (0,), lambda *_: 1, count=1)
