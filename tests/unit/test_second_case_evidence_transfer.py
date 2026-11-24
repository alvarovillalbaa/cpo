from benchmarks.second_case_evidence_transfer import (
    KEEP, SCRIPT, SUMMARY, VETO, Opportunity, ceilings, paid_keys, rule, settlement,
)


def event(subject, key, gain, cost=0):
    return Opportunity(subject, {SUMMARY: key, SCRIPT: key, 'complete-pairs': key},
                       (gain < 0,), (gain > 0,), cost)


def test_paid_keys_ignore_prompt_and_case_names():
    def keys(base, candidate, v, q):
        ledger = {('qualification', base, str(q[0])): True, ('qualification', base, str(q[1])): False,
                  ('validation', base, str(v[1])): False, ('validation', candidate, str(v[1])): True,
                  ('qualification', candidate, str(q[1])): True}
        return paid_keys(base, candidate, [candidate], ((), v, q, ()), ledger)

    assert keys('a', 'b', (1, 8), (3, 7)) == keys('resume', 'other', (9, 4), (6, 5))


def test_fit_requires_multiple_discovery_tasks_and_positive_pool_gain():
    events = [event('a', 'one-task', 1), event('a', 'one-task', 1),
              event('a', 'mixed', 1), event('b', 'mixed', -1),
              event('b', 'wins', 1), event('c', 'wins', 1)]
    result = rule(events, SUMMARY, 2)
    assert result == {'supported': ['mixed', 'wins'], 'vetoes': ['wins']}
    target = [event('new', 'wins', 1, 7), event('new', 'unseen', 1, -4)]
    baseline = {'holdoutPasses': 10, 'paidLookups': 20}
    assert settlement(baseline, target, SUMMARY, {SUMMARY: result}) == {
        'holdoutPasses': 11, 'paidLookups': 27, 'vetoed': 1}
    assert settlement(baseline, target, KEEP, {}) == {**baseline, 'vetoed': 0}
    assert settlement(baseline, target, VETO, {}) == {'holdoutPasses': 12, 'paidLookups': 23, 'vetoed': 2}


def test_equal_paid_evidence_can_hide_opposite_downstream_effects():
    events = [event('a', 'same', 1), event('a', 'same', -1), event('b', 'different', 1)]
    policies = {feature: rule(events, feature, 2) for feature in (SUMMARY, SCRIPT)}
    result = ceilings(events, policies)
    assert result['vetoGainWithPerEventHindsight'] == 2
    assert result[SUMMARY]['vetoGainWithClassHindsight'] == 1
    assert result[SUMMARY]['mixedSignClasses'] == 1
    assert result[SUMMARY]['supportedEvents'] == 0
