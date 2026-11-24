from collections import Counter, defaultdict
import pytest

from benchmarks.settled_episode_qualification_feedback import (
    ALWAYS, ANY, CONDITIONAL, OUTCOMES, fit_tables, outcome, rollout_graph, rule,
)
from benchmarks.settled_episode_refit import RETAIN
from cpo.bounded_uniform_validation import run_bounded_uniform_cycle
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.paired_qualification import QualificationDecision, QualificationObservation
from cpo.single_finalist import FinalistResult


def test_switch_uses_only_the_previous_cycle_and_carries_its_actual_incumbent():
    cells = {
        'start': (0, 0, 0, 0, 0, 0, 0),
        'first': (1, 1, 1, 0, 0, 0, 0),
        'second': (0, 0, 0, 1, 1, 0, 0),
        'third': (0, 0, 0, 0, 0, 1, 1),
    }
    stages = ((1, ('first',), ((), (0,), (1,), (2,))),
              (2, ('second',), ((), (3,), (4,), (2,))),
              (3, ('third',), ((), (5,), (6,), (2,))))
    plan = {'controls': (('uniform', 'uniform', 1, 2),)}
    rollout, clear = rollout_graph(plan, cells, stages, {'uniform': run_bounded_uniform_cycle})

    assert rollout('start', rule('uniform', 'promoted', RETAIN)) == ([0], 8, ('promoted', 'skipped', 'promoted'), 1)
    assert rollout('start', rule('uniform', ANY, RETAIN)) == ([1], 4, ('promoted', 'skipped', 'skipped'), 2)
    assert rollout('start', rule('uniform', 'finalist-rejected', RETAIN)) == ([0], 12, ('promoted',) * 3, 0)
    clear()


@pytest.mark.parametrize(('nominee', 'promoted', 'grades', 'expected'), (
    (None, False, (True,) * 4, 'precheck-closed'),
    (None, False, (False,), 'no-finalist'),
    ('alternative', False, (False, False), 'finalist-rejected'),
    ('alternative', True, (False, True), 'promoted'),
))
def test_outcome_classifies_only_observed_qualification_evidence(nominee, promoted, grades, expected):
    observations = tuple(QualificationObservation('base', str(index), 0, grade)
                         for index, grade in enumerate(grades))
    qualification = QualificationDecision('promoted' if promoted else 'rejected',
                                           nominee if promoted else 'base', observations, 0, 1)
    result = FixedPoolCycleResult(FinalistResult(nominee or 'base', nominee, 0), qualification)
    assert outcome(result) == expected


def test_fit_uses_trigger_support_and_prices_the_opening_probe():
    anchors = {'base': ('base',) * 3}
    budget = {'cohort': 26}
    counts = {'cohort': Counter({False: 1, True: 2})}
    awarded = defaultdict(Counter)
    support = defaultdict(set)
    for state in range(3):
        support['base', state, ANY].update(('a', 'b', 'c'))
        awarded['cohort', state, rule('base')] = Counter(paidLookups=8, holdoutPasses=4)
        for trigger in (ANY, *OUTCOMES):
            awarded['cohort', state, rule('base', trigger, 'alternate')] = Counter(paidLookups=8, holdoutPasses=4)
        awarded['cohort', state, rule('base', 'promoted', 'alternate')] = Counter(
            paidLookups=4, holdoutPasses=12 if state == 1 else 20,
        )
    support['base', 1, 'promoted'].update(('a', 'b', 'c'))

    report = fit_tables(anchors, ('base', 'alternate'), budget, counts, awarded, support, 3)
    winner = report['policies'][CONDITIONAL]
    assert winner['rules'] == (rule('base'), rule('base', 'promoted', 'alternate'), rule('base'))
    assert winner['points'] == {'cohort': {'holdoutPasses': 20, 'paidLookups': 26}}
    assert report['policies'][ALWAYS]['rules'] == (rule('base'),) * 3
