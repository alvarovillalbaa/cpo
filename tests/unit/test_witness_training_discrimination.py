from itertools import combinations
from random import Random

from benchmarks import witness_training_discrimination as study


def test_cover_is_smallest_and_keeps_the_earliest_subset_on_a_tie():
    rows = [{'id': 'a', 'features': {'one', 'two'}}, {'id': 'b', 'features': {'three'}},
            {'id': 'c', 'features': {'one', 'three'}}, {'id': 'd', 'features': {'two'}}]
    selected = study.minimum_cover(rows, lambda row: row['features'])

    assert [row['id'] for row in selected] == ['a', 'b']
    assert all(set().union(*(row['features'] for row in subset)) != {'one', 'two', 'three'}
               for count in range(len(selected)) for subset in combinations(rows, count))


def test_original_exact_grader_distinguishes_the_thirty_minute_boundary():
    policy = study.coverage.policy
    rows = []
    for index, duration in enumerate((29, 30)):
        inputs, expected, critical = policy.outage(index, Random(11), (duration, 'STANDARD', False, 'POSTED'))
        rows.append({'input': inputs, 'expected': expected, 'critical': critical})

    assert 'pay-below-thirty' in study.distinguishing_faults('outage', rows[0])
    assert 'exclude-thirty' not in study.distinguishing_faults('outage', rows[0])
    assert 'exclude-thirty' in study.distinguishing_faults('outage', rows[1])
    assert 'pay-below-thirty' not in study.distinguishing_faults('outage', rows[1])


def test_selector_is_independent_of_scoring_panels_and_preserves_full_training_signals():
    regions = study.EPISODE.cohorts()['warehouse']
    actual = study.compare('warehouse', regions)
    stripped = study.compare('warehouse', {**regions, 'holdout': [], 'confirmation': []})

    for full, empty in zip(actual, stripped, strict=True):
        assert full['minimumCover']['cases'] == empty['minimumCover']['cases']
        assert full['minimumCover']['coveredSignals'] == full['full']['coveredSignals']
        assert full['minimumCover']['unresolvedScoringFaults'] == full['full']['unresolvedScoringFaults']
        assert len(full['minimumCover']['cases']) == len(full['prefix']['cases'])
