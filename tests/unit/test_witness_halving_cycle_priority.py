from collections import Counter

from benchmarks import witness_halving_cycle_priority as replay


def boards():
    first = {'alternatives': ['first', 'other'], 'validation': [0, 1, 2]}
    second = {'alternatives': ['backup', 'rival'], 'validation': [3, 4, 5]}
    paid = {(prompt, case): prompt == 'backup' for prompt in ('start', 'backup', 'rival') for case in range(3, 6)}
    return first, second, paid


def test_certificate_orders_a_known_challenger_before_an_unresolved_cycle():
    first, second, paid = boards()
    assert replay.priority('start', second, paid) == (True, 1)
    assert replay.priority('start', first, paid) < replay.priority('start', second, paid)
    assert not replay.priority('start', first, paid)[0]


def test_later_cache_only_cycle_can_nominate_without_reopening_the_shared_cap():
    first, second, paid = boards()
    activity = Counter()
    purchases = []

    def evaluate(prompt, case):
        purchases.append((prompt, case))
        return False

    result = replay.fallback('start', [first, second], paid, evaluate, 1, activity, rank_cycles=False)

    assert result.original == 'backup'
    assert result.paid_search == len(paid) + len(purchases) == len(paid) + 1
    assert activity == {'cycles': 2, 'unfinishedCycles': 1, 'nominations': 1}
    assert all(result.grades[key] == grade for key, grade in paid.items())


def test_ranking_uses_no_new_lookup_when_a_later_winner_is_known():
    first, second, paid = boards()
    activity = Counter()

    def evaluate(prompt, case):
        raise AssertionError(f'Unexpected lookup for {prompt} on {case}')

    result = replay.fallback('start', [first, second], paid, evaluate, 16, activity, rank_cycles=True)

    assert result.original == 'backup'
    assert result.paid_search == len(paid)
    assert activity == {'cycles': 1, 'nominations': 1}
