from itertools import product

import pytest

from benchmarks.settled_episode_refit import fit_table
from benchmarks.language_roster_budget_frontier import Point, RETAIN
from cpo.settled_episode_schedule import choose_schedule


def execute(grades, actions):
    paid = []

    def read(prompt, row):
        assert prompt == 'base'
        paid.append(row)
        return grades[row]

    result = choose_schedule('base', range(len(grades)), read, actions=actions)
    assert paid == list(range(len(paid)))
    return result, len(paid)


@pytest.mark.parametrize('length', range(5))
def test_stops_at_the_first_decision_that_every_completion_shares(length):
    for actions in product('abc', repeat=length + 1):
        for grades in product((False, True), repeat=length):
            action, reads = execute(grades, actions)
            assert action == actions[sum(grades)]
            prefix = sum(grades[:reads])
            assert len(set(actions[prefix:prefix + length - reads + 1])) == 1
            if reads:
                earlier = sum(grades[:reads - 1])
                assert len(set(actions[earlier:earlier + length - reads + 2])) > 1


@pytest.mark.parametrize('settled', (False, True))
def test_fitter_prices_every_table_against_the_actual_training_callback(settled):
    options = (RETAIN, 'wide', 'narrow')
    rows = []
    for i, pair in enumerate(product((False, True), repeat=2)):
        points = {RETAIN: Point(5, 0, (RETAIN,)), 'wide': Point(9-i, 4, ('wide',)),
                  'narrow': Point(7+i, 2, ('narrow',))}
        rows.append(('cohort', str(i), pair, points))
    for budget in range(8, 26):
        expected = []
        for table in product(options, repeat=3):
            score, cost = 0, 0
            for _, _, grades, menu in rows:
                choice, reads = execute(grades, table)
                point = menu[choice]
                cost += point.cost + (reads if settled else 2)
                score += point.passes
            if cost <= budget:
                expected.append((-score, cost, table))
        score, cost, table = min(expected)
        fitted = fit_table(rows, options, {'cohort': budget}, 1, settled=settled)
        assert fitted['actions'] == table
        assert fitted['points'] == {'cohort': {'holdoutPasses': -score, 'paidLookups': cost}}
