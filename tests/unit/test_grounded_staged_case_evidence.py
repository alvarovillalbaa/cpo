"""T2 fixture verification of paired case sensitivity and archive integrity."""

from collections import Counter
from itertools import product

import pytest

from benchmarks import grounded_staged as staged, grounded_staged_fixture as fixture
from benchmarks.grounded_staged_case_evidence import case_resampling_range, verify
from cpo._contract import digest


def test_range_matches_exhaustive_stratified_case_resampling():
    first, second = (-2, 0, 1, 2), (0, 2, 2)
    distribution = Counter(sum(a) + sum(b) for a in product(first, repeat=len(first))
                           for b in product(second, repeat=len(second)))
    values = sorted(distribution.elements())
    size = len(values)
    assert case_resampling_range((first, second)) == [values[(size - 1) // 40], values[(39 * size - 1) // 40]]


def test_perfect_two_repeat_wins_remain_two_case_wins():
    assert case_resampling_range(([2, 2, 0, 0, 0, 0, 0, 0], [0] * 8, [0] * 8)) == [0, 10]


def test_case_evidence_replays_archives_and_rejects_changed_results(tmp_path):
    development = tmp_path / 'development'
    confirmation = tmp_path / 'confirmation'
    _, development_plan, _ = staged.prepare()
    staged.run(digest(development_plan), development, fixture.respond, delivery='fixture')
    _, confirmation_plan, _ = staged.prepare(development)
    staged.run(digest(confirmation_plan), confirmation, fixture.respond, delivery='fixture', development=development)

    trial = verify(development)
    panel = verify(confirmation, development=development)
    assert trial['sealedGateQualified'] and panel['sealedGateQualified']
    assert trial['pairedRepliesPerArm'] == 108
    assert sum(trial['uniqueCasesByTask'].values()) == 54
    assert trial['comparisons']['gepa-sequential']['casesAhead'] == 4
    assert panel['pairedRepliesPerArm'] == 48
    assert sum(panel['uniqueCasesByTask'].values()) == 24
    sequential = panel['comparisons']['gepa-sequential']
    assert sequential['casesAhead'] == 2
    assert sequential['caseResampling95PassDifference'] == [0, 10]

    result = confirmation / 'result.json'
    result.write_bytes(result.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='differs from the saved results'):
        verify(confirmation, development=development)
