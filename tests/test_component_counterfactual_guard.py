from benchmarks.component_conditional_edits import score
from benchmarks.component_counterfactual_guard import guard_candidate
from benchmarks.component_merge import encode


FALLBACK = {'aggregate': 'guarded', 'precedence': 'guarded', 'eligibility': 'guarded'}
CANDIDATE = {**FALLBACK, 'aggregate': 'scope:guarded:broad'}


def fixture(forbids):
    validation = {
        'legacy': {'id': 'legacy', 'family': forbids, 'critical': True, 'interaction': False,
                   'needs': [], 'forbids': [forbids]},
        'interaction': {'id': 'interaction', 'family': 'aggregate', 'critical': True, 'interaction': True,
                        'needs': ['aggregate', 'precedence'], 'forbids': ['eligibility']},
    }
    journal = {(encode(program), case): score(program, row, 'routing').passed
               for program in (FALLBACK, CANDIDATE) for case, row in validation.items()}
    return validation, journal


def test_guard_rejects_a_clean_improvement_that_is_unsafe_when_the_label_flips():
    validation, journal = fixture('aggregate')
    results = guard_candidate(encode(CANDIDATE), journal, validation, 'routing', 1)
    clean, disposition = results['clean-gate']
    assert clean == encode(CANDIDATE) and disposition['evaluations'] == 0
    protected, evidence = results['counterfactual-gate']
    assert protected == encode(FALLBACK)
    assert evidence['status'] == 'critical_regression'
    assert evidence['observations'] == [('legacy:opposite', False)]


def test_guard_requires_funds_for_every_required_probe_and_reuses_nominal_evidence():
    validation, journal = fixture('eligibility')
    winner, funded = guard_candidate(encode(CANDIDATE), journal, validation, 'routing', 1)['counterfactual-gate']
    assert winner == encode(CANDIDATE) and funded['status'] == 'promote'
    assert funded['observations'] == [('legacy:opposite', True)]
    fallback, unfunded = guard_candidate(encode(CANDIDATE), journal, validation, 'routing', 0)['counterfactual-gate']
    assert fallback == encode(FALLBACK)
    assert unfunded['status'] == 'budget' and unfunded['evaluations'] == 0
