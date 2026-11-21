from collections import Counter
from itertools import product

from benchmarks import witness_paid_anchor_bounds as replay


def test_exact_and_proved_nominations_agree_with_all_binary_grades_on_a_small_board():
    candidates, anchors = ('start', 'first', 'second'), (0, 1)
    keys = tuple(product(candidates, anchors))
    for grades in product((False, True), repeat=len(keys)):
        board = dict(zip(keys, grades, strict=True))

        def score(prompt):
            return sum(board[prompt, case] for case in anchors)

        for included in product((False, True), repeat=len(keys)):
            paid = {key: board[key] for key, present in zip(keys, included, strict=True) if present}
            for cap in (0, 2, len(keys)):
                spent = set()

                def evaluate(prompt, case):
                    key = prompt, case
                    assert key not in paid and key not in spent
                    spent.add(key)
                    return board[key]

                result = replay.race(candidates, anchors, paid, evaluate, cap, allow_proved_gain=True)

                assert result.reads == len(spent) <= cap
                if result.settled:
                    assert result.prompt == max(candidates, key=score)
                elif result.prompt != 'start':
                    assert score(result.prompt) > score('start')
                assert cap < len(keys) or result.settled


def test_proved_gain_can_fund_one_proof_when_the_winning_identity_is_unresolved():
    candidates, anchors = ('start', 'first', 'second'), (0, 1)
    paid = {('start', 0): False, ('start', 1): False, ('first', 0): True}

    def evaluate(prompt, case):
        raise AssertionError(f'The cap does not fund {prompt} on {case}')

    exact = replay.race(candidates, anchors, paid, evaluate, 0, allow_proved_gain=False)
    proved = replay.race(candidates, anchors, paid, evaluate, 0, allow_proved_gain=True)

    assert exact.prompt == 'start'
    assert proved.prompt == 'first'
    assert not exact.settled and not proved.settled


def test_fallback_carries_paid_bounds_and_one_shared_budget_across_cycles():
    layouts = [{'seed': 8, 'validation': [0, 1, 2, 3], 'alternatives': ['first']},
               {'seed': 9, 'validation': [0, 1, 2, 4], 'alternatives': ['second']}]
    paid = {('start', case): True for case in range(3)}
    activity, purchases = Counter(), []

    def evaluate(prompt, case):
        purchases.append((prompt, case))
        return True

    result = replay.fallback('start', layouts, paid, evaluate, 1, activity, allow_proved_gain=True)

    assert result.original is None
    assert purchases == [('start', 3)]
    assert result.paid_search == 4
    assert activity == {'races': 2, 'preloadedGrades': 6, 'cappedEpisodes': 1}
