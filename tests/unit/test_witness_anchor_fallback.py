from collections import Counter

from benchmarks import witness_anchor_fallback as replay


def layout(*candidates):
    return {'seed': 8, 'validation': [0, 1, 2, 3], 'alternatives': candidates}


def test_exact_cached_winner_can_settle_without_buying_another_grade():
    paid = {('incumbent', case): False for case in range(4)}
    paid.update({('candidate', case): True for case in range(4)})
    activity = Counter()

    def evaluate(prompt, case):
        raise AssertionError(f'Unexpected purchase for {prompt} on {case}')

    nomination = replay.cached_race('incumbent', [layout('candidate')], paid, evaluate, 0, activity)

    assert nomination.original == 'candidate'
    assert nomination.paid_search == len(paid)
    assert nomination.grades == paid
    assert activity == {'cacheHits': 5, 'nominations': 1, 'races': 1}


def test_lookup_cap_is_shared_and_an_unsettled_race_never_nominates():
    purchases = []
    paid = {('incumbent', 0): True}
    activity = Counter()

    def evaluate(prompt, case):
        purchases.append((prompt, case))
        return prompt == 'incumbent'

    layouts = [layout('first'), {**layout('second'), 'validation': [4, 5, 6, 7]}]
    nomination = replay.cached_race('incumbent', layouts, paid, evaluate, 4, activity)

    assert nomination.original is None
    assert len(purchases) == 4
    assert len(set(purchases)) == 4
    assert ('incumbent', 0) not in purchases
    assert nomination.paid_search == 5
    assert activity['races'] == 2
    assert activity['cappedEpisodes'] == 1
    assert paid == {('incumbent', 0): True}


def test_a_settled_challenger_ends_the_fallback_before_later_cycles():
    purchases = []

    def evaluate(prompt, case):
        purchases.append((prompt, case))
        return prompt != 'incumbent'

    result = replay.cached_race('incumbent', [layout('first'), layout('second')], {}, evaluate, 8, Counter())

    assert result.original == 'first'
    assert result.paid_search == len(purchases) == 5
    assert {prompt for prompt, _ in purchases} == {'incumbent', 'first'}
