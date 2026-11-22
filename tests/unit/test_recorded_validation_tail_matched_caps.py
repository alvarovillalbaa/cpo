from collections import Counter
from random import Random

from benchmarks import recorded_validation_tail_matched_caps as study


def test_matched_budgets_reselect_both_suites_after_each_paired_draw():
    vectors = {
        'subject': {
            study.RETAIN: (0, 0),
            'cpo-low': (1, 2),
            'cpo-high': (4, 0),
            'cpo-duplicate': (4, 0),
            'gepa-low': (0, 1),
            'gepa-high': (0, 4),
        },
    }
    spend = {study.RETAIN: 0, 'cpo-low': 1, 'cpo-high': 2, 'cpo-duplicate': 3, 'gepa-low': 1, 'gepa-high': 2}
    totals = {label: {'holdoutPasses': sum(grade), 'paidLookups': spend[label]}
              for label, grade in vectors['subject'].items()}
    groups = {'cpo': ('cpo-low', 'cpo-high', 'cpo-duplicate'), 'gepa': ('gepa-low', 'gepa-high')}
    result = study.common_frontiers(vectors, totals, groups, (0, 1, 3),
                                    {'bootstrapSeed': 3, 'bootstrapDraws': 256})
    assert result['0']['settings']['cpo']['setting'] == result['0']['settings']['gepa']['setting'] == study.RETAIN
    assert result['1']['settings']['cpo']['setting'] == 'cpo-low'
    assert result['1']['passDelta'] == 2
    assert result['3']['settings']['cpo']['setting'] == 'cpo-high'
    assert result['3']['settings']['gepa']['setting'] == 'gepa-high'
    rng = Random(3)
    differences = []
    for _ in range(256):
        weights = Counter(rng.randrange(2) for _ in range(2))
        first, second = weights[0], weights[1]
        differences.append(max(first + 2 * second, 4 * first) - 4 * second)
    assert result['3']['pairedCaseRange95'] == study.prior.frontier.interval(differences)


def test_every_cap_on_an_aligned_panel_reconciles_to_the_full_pool():
    matrix = ['01' * 20, '10' * 20, '01' * 10 + '10' * 10]
    subject = 'archived-example'
    heldout = study.prior.reference_runner.language.source.holdout(subject, len(matrix[0]))
    plan = {'caseCounts': (10, 6, 4), 'minimumSearchCap': 6, 'maximumSweptCpoCap': 18,
            'challengers': 2, 'searchCap': 180, 'seeds': (1, 7, 21)}
    totals, vectors, traces = study.cpo_panel(subject, matrix, plan, len(heldout))
    assert len(totals) == len(vectors) == 1 + 13 * len(study.prior.POLICIES)
    assert set(traces) == set(study.prior.POLICIES)
    for policy in study.prior.POLICIES:
        assert totals[f'{policy}/6']['holdoutPasses'] == totals[study.RETAIN]['holdoutPasses']
    assert all(sum(vectors[label]) == row['holdoutPasses'] for label, row in totals.items())
