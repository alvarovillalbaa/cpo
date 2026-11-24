import pytest

from benchmarks.episode_training_probe_transfer import fit_table
from benchmarks.language_roster_budget_frontier import RETAIN, Point
from cpo.episode_probe import observe_training_prefix


def test_paired_probe_reads_only_the_first_challenger_and_shared_training_prefix():
    ledger = []

    def evaluate(prompt, case):
        ledger.append((prompt, case))
        return prompt == 'first' and case == 0

    state = observe_training_prefix('base', ('first', 'later'), (0, 1, 2), evaluate, count=2, paired=True)
    assert state == '1'
    assert ledger == [('base', 0), ('first', 0), ('base', 1), ('first', 1)]


def test_no_probe_is_free_and_nonboolean_grades_are_rejected():
    assert observe_training_prefix('base', (), (), None, count=0, paired=False) == '0'
    with pytest.raises(ValueError, match='exact boolean'):
        observe_training_prefix('base', (), (0,), lambda *_: 1, count=1, paired=False)


def test_table_counts_probe_cost_on_retention_and_requires_multiple_subjects():
    deck = {RETAIN: Point(2, 0, (RETAIN,)), 'search': Point(3, 3, ('search',))}
    rows = [('cohort', 'one', 'weak', 1, deck), ('cohort', 'two', 'weak', 1, deck),
            ('cohort', 'three', 'strong', 1, deck)]
    actions = (RETAIN, 'search')
    fit = fit_table(rows, actions, {'cohort': 9}, 2)
    assert fit['actions'] == {'weak': 'search', 'strong': RETAIN}
    assert fit['points'] == {'cohort': {'holdoutPasses': 8, 'paidLookups': 9}}
    constrained = fit_table(rows, actions, {'cohort': 8}, 2)
    assert constrained['actions'] == {'weak': RETAIN, 'strong': RETAIN}
    assert constrained['points'] == {'cohort': {'holdoutPasses': 6, 'paidLookups': 3}}
