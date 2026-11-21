from collections import Counter

from benchmarks import grounded, grounded_staged as staged, grounded_witness_episode as episode
from benchmarks import typed_policy as policy, witness_regime_coverage as audit


def test_supplement_is_disjoint_and_covers_exactly_the_confirmation_gaps():
    groups = episode.cohorts()
    prior = policy.cohorts(grounded.SEED), staged.cohorts()
    supplement = audit.stress_cases(groups, prior)
    for task, rows in supplement.items():
        sealed = {row['input'] for source in (groups, *prior) for split in source[task].values() for row in split}
        unique = {row['input'] for row in rows}
        assert len(unique) == len(rows)
        assert unique.isdisjoint(sealed)
        present = {audit.regime(task, row) for row in groups[task]['confirmation']}
        observed = {audit.regime(task, row) for row in rows}
        assert observed == set(audit.REGIMES[task]) - present
        assert len(observed) == len(rows)


def test_actual_confirmation_gate_distinguishes_visible_errors_only_against_exact_control():
    receipt = audit.summarize()
    results = receipt['results']
    for task, item in results.items():
        for trial in item['tests']:
            mismatch = trial['mismatchedRowsByPanel']['confirmation']
            assert trial['qualified']['confirmation']['exactControl'] is (mismatch == 0)
            assert trial['stressDetects'] is (mismatch == 0)
        assert item['confirmationMissedByExactControl'] == item['regimeCount'] - item['regimesByPanel']['confirmation']
    assert results['warehouse']['regimesByPanel']['confirmation'] == 8
    assert results['warehouse']['invisibleInBothSealedScoringPanels'] == 6
    assert receipt['alternativeWarehouseConfirmation']['invisibleInBothScoringPanels'] == 0


def test_alternative_panel_keeps_size_balance_and_disjointness():
    groups = episode.cohorts()
    warehouse = groups['warehouse']
    supplement = audit.stress_cases(groups, (policy.cohorts(grounded.SEED), staged.cohorts()))
    panel = audit.balanced_confirmation(groups, supplement)
    original = warehouse['confirmation']
    assert len(panel) == len(original) == 8
    assert len({row['input'] for row in panel} & {row['input'] for row in original}) == 2
    assert {row['input'] for row in panel}.isdisjoint(row['input'] for row in warehouse['holdout'])
    assert sum(row['critical'] for row in panel) == sum(row['critical'] for row in original)
    for axis in (2, 3):
        assert Counter(audit.regime('warehouse', row)[axis] for row in panel) == Counter(
            audit.regime('warehouse', row)[axis] for row in original)
    assert {audit.regime('warehouse', row) for row in (*panel, *warehouse['holdout'])} == set(policy.WAREHOUSE)
