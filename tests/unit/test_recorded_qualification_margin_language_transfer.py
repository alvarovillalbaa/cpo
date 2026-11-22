import pytest

from benchmarks import recorded_qualification_margin_language_transfer as study


def test_language_transfer_requires_aligned_case_and_prompt_axes():
    def panel(cohort, model):
        return {'benchmark': cohort, 'subject': f'{cohort}-test', 'model': model, 'correctness': ['01' * 15] * 100,
                'caseIDs': list(range(30)), 'templateIDs': [[index, 0] for index in range(100)]}

    panels = [panel(cohort, model) for cohort in study.COHORTS for model in ('one', 'two')]
    assert all(len(group) == 2 for group in study.load_panels(panels).values())
    with pytest.raises(ValueError, match='both model panels'):
        study.load_panels(panels[:-1])
    panels[-1]['templateIDs'].reverse()
    with pytest.raises(ValueError, match='case and template order'):
        study.load_panels(panels)


def test_qualification_effect_resamples_paired_grades_within_each_subject():
    scores = {'a': {study.BASELINE: [0, 2], study.CANDIDATE: [1, 3]},
              'b': {study.BASELINE: [3, 4, 5], study.CANDIDATE: [1, 2, 3]}}
    effect = study.paired_effect(scores, {'bootstrapSeed': 21, 'bootstrapDraws': 64})
    assert effect == {'passDifference': -4, 'pairedRange95': [-4, -4]}
