from itertools import product

import pytest

from benchmarks.language_roster_budget_frontier import Point
from benchmarks.settled_episode_cohort_guard import guarded_table
from benchmarks.settled_episode_refit import RETAIN
from cpo.settled_episode_schedule import choose_schedule


@pytest.mark.parametrize('min_subjects', (1, 2))
def test_cohort_guard_matches_enumerated_paid_routes(min_subjects):
    options = ('anchor', 'fast', 'uneven', RETAIN)
    floors = {
        'A': {'holdoutPasses': 11, 'paidLookups': 15},
        'B': {'holdoutPasses': 11, 'paidLookups': 14},
    }
    rows = []
    for cohort in floors:
        for index, pair in enumerate(product((False, True), repeat=2)):
            if cohort == 'B' and index == 3:
                continue
            menu = {
                'anchor': Point(3 + (cohort == 'B'), 3, ('anchor',)),
                'fast': Point(3 + (index == 0) + (cohort == 'B'), 2, ('fast',)),
                'uneven': Point(1 if cohort == 'B' else 6, 2, ('uneven',)),
                RETAIN: Point(3 + (cohort == 'B'), 0, (RETAIN,)),
            }
            rows.append((cohort, str(index), pair, menu))

    candidates = []
    for actions in product(options, repeat=3):
        if any(len({subject for _, subject, pair, _ in rows if sum(pair) == state}) < min_subjects
               and actions[state] != RETAIN for state in range(3)):
            continue
        points = {cohort: dict(holdoutPasses=0, paidLookups=0) for cohort in floors}
        for cohort, _, pair, menu in rows:
            paid = []

            def read(prompt, index):
                paid.append(index)
                return pair[index]

            action = choose_schedule('incumbent', range(2), read, actions=actions)
            points[cohort]['holdoutPasses'] += menu[action].passes
            points[cohort]['paidLookups'] += menu[action].cost + len(paid)
        if all(floor['holdoutPasses'] <= points[cohort]['holdoutPasses']
               and floor['paidLookups'] >= points[cohort]['paidLookups'] for cohort, floor in floors.items()):
            candidates.append((-sum(point['holdoutPasses'] for point in points.values()),
                               sum(point['paidLookups'] for point in points.values()), actions, points))

    _, _, actions, points = min(candidates)
    actual = guarded_table(rows, options, floors, min_subjects)
    assert actual == {'actions': actions, 'points': points,
                      'feasibleTables': len(candidates), 'support': [1, 2, 1]}
