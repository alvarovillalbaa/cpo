"""T2 checks for evidence-only decisions and held-out-family isolation."""

from dataclasses import replace

from benchmarks import witness_fallback_routing as study


def unit(name, positive):
    return {'held': [0], 'decisionsPerCase': 2, 'opportunities': [
        study.Opportunity((name, 0), 1, 5, 5, 0, (positive,), 4),
        study.Opportunity((name, 1), 4, 5, 24, 0, (0,), 6),
    ]}


def test_routing_decisions_use_neither_future_accuracy_nor_future_cost():
    candidate = study.Opportunity(('sample', 0), 1, 5, 16, 1, (1,), 30)
    changed = replace(candidate, deltas=(-1,), addedLookups=9999)
    for rule in (study.NEVER, study.ALWAYS, *study.PAID_RULES, *study.BLIND_RULES):
        assert study.accept(rule, candidate) == study.accept(rule, changed)
    assert study.accept('incumbent-at-most-30%-pass', candidate)
    assert study.accept('at-least-one-paired-win', candidate)
    assert not study.accept('at-most-12-paid-grades', candidate)


def test_fit_excludes_rules_that_exceed_the_training_budget():
    groups = {'train': unit('training', 1)}
    rule, cap = study.fit(groups, (study.ALWAYS, study.NEVER, 'incumbent-at-most-30%-pass'), 50)
    assert cap == 5 and rule == 'incumbent-at-most-30%-pass'


def test_family_labels_never_choose_their_own_rule():
    plan = {'trainingLookupLimitPercent': 50, 'pairedCaseDraws': 32, 'resamplingSeed': 17}
    source = {'one': {'target-one': unit('holdout', 1)}, 'two': {'target-two': unit('training', 1)}}
    old = study.cross_fit(plan, source)['one']
    source['one']['target-one'] = unit('holdout', -1)
    changed = study.cross_fit(plan, source)['one']
    assert old['trainingSubjects'] == changed['trainingSubjects'] == ['target-two']
    assert old['paidRule'] == changed['paidRule']
    assert old['blindRule'] == changed['blindRule']
    assert old['routed']['addedPasses'] == 1 and changed['routed']['addedPasses'] == -1
