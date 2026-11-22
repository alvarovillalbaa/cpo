import pytest

from benchmarks import recorded_low_cap_mmlu_transfer as study


def test_transfer_enrollment_rejects_either_kind_of_overlap_and_duplicate_panels():
    source = [('MMLU', 'known-subject', 'known-model'), ('BBH', 'different', 'known-bbh-model')]
    new = ('MMLU', 'new-subject', 'new-model', [])
    study.check_enrollment(source, [new, ('MMLU', 'new-subject', 'another-model', [])])
    for target in (('MMLU', 'known-subject', 'new-model', []),
                   ('MMLU', 'new-subject', 'known-model', []),
                   ('MMLU', 'new-subject', 'known-bbh-model', []),
                   ('BBH', 'new-subject', 'new-model', [])):
        with pytest.raises(ValueError, match='outside the cap sweep'):
            study.check_enrollment(source, [target])
    with pytest.raises(ValueError, match='enrolled twice'):
        study.check_enrollment(source, [new, new])


def test_capped_replay_reconciles_paid_queries_and_heldout_cases():
    plan = {'caseCounts': (10, 6, 4), 'challengers': 2, 'seeds': (1, 7, 21),
            'candidate': study.PRIMARY, 'fullValidationDiagnostic': study.FULL}
    matrix = ['01' * 20, '10' * 20, '01' * 10 + '10' * 10]
    totals, vectors, diagnostics = study.measure_cpo('three-prompts', matrix, plan)
    assert set(totals) == {study.PRIMARY, study.FULL, study.frontier.RETAIN}
    assert diagnostics['trials'] == len(plan['seeds'])
    for label, point in totals.items():
        assert point['holdoutPasses'] == sum(vectors[label])
        assert point['paidLookups'] == point['searchLookups'] + point['qualificationLookups']
    assert totals[study.PRIMARY]['searchLookups'] <= 13 * len(plan['seeds'])
    groups = diagnostics['deploymentChanges'].values()
    assert sum(group['trials'] for group in groups) == len(plan['seeds'])
    for change, total in (('fullPoolPassDelta', 'holdoutPasses'), ('extraFullPoolLookups', 'paidLookups')):
        assert sum(group[change] for group in groups) == totals[study.FULL][total] - totals[study.PRIMARY][total]
