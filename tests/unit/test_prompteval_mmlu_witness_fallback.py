"""T2 checks for a single shared proof and same-cost comparator selection."""

from benchmarks import prompteval_mmlu_witness_fallback as study


def test_spent_witness_admission_blocks_fallback_even_after_rejection(monkeypatch):
    monkeypatch.setattr(study.original, 'play', lambda *args: ('retain', 19, 'trace', {}, 4))

    def unexpected(*args):
        raise AssertionError('A failed witness proof spent the only admission')

    monkeypatch.setattr(study.capped, 'transfer_trial', unexpected)
    first, fallback, evidence = study.selection(None, None, None, None, None, None)
    assert first == fallback == ('retain', 19, 'trace')
    assert not evidence


def test_mmlu_comparison_equal_weights_subjects_and_includes_original_witness():
    native = {'small-gepa': {}, 'over-budget': {}}
    controls = (*study.HALVING, *native)

    def panel(size, candidate, witness):
        return {'caseIds': list(range(size)), 'decisionsPerCase': 1,
                'cases': {study.CANDIDATE: candidate, study.BASE: witness, study.START: [0] * size,
                          **{name: [int(name == 'over-budget')] * size for name in controls}},
                'paidLookups': {study.CANDIDATE: 10, study.BASE: 9, study.START: 0,
                               **{name: 11 if name == 'over-budget' else 8 for name in controls}}}

    groups = {'small': panel(1, [0], [1]), 'large': panel(3, [1, 1, 1], [0, 1, 0])}
    output = study.summarize({'nativeSettings': native, 'draws': 128, 'seed': 42}, groups)
    assert output['totals'][study.CANDIDATE]['holdoutPasses'] == 3
    assert output['totals'][study.CANDIDATE]['macroAccuracy'] == '1/2'
    assert output['comparisons']['allControls']['strongestAffordableFixed'] == study.BASE
    assert output['comparisons']['native']['strongestAffordableFixed'] == study.START
    assert 'over-budget' not in output['comparisons']['allControls']['controlSelections']['fixedSubjects']
