"""T2 brute-force check of realized-budget allocation over audit directions."""

from itertools import product

from benchmarks.quoted_schedule_realized_frontier import RETAIN, optimum_by_budget


def test_common_and_mixed_choices_attain_the_exact_affordable_optima():
    def point(score, price):
        return {'holdoutPasses': score, 'paidLookups': price}

    points = {'task/0': {RETAIN: point(4, 0), 'wide': point(9, 4), 'deep': point(7, 2)},
              'task/1': {RETAIN: point(3, 0), 'wide': point(4, 1), 'deep': point(9, 3)}}
    budgets = {str(i): i for i in range(9)}
    result = optimum_by_budget(points, budgets)
    for name, budget in budgets.items():
        for scope in ('common', 'mixed'):
            candidates = []
            for first, second in product(*points.values()):
                if scope == 'common' and first != second:
                    continue
                a, b = points['task/0'][first], points['task/1'][second]
                cost = a['paidLookups'] + b['paidLookups']
                if cost <= budget:
                    candidates.append((-(a['holdoutPasses'] + b['holdoutPasses']), cost))
            score, cost = min(candidates)
            measured = result[name][scope]
            assert (measured['holdoutPasses'], measured['paidLookups']) == (-score, cost)
            attending = [points[direction][setting] for direction, setting in measured['settingsByDirection'].items()]
            assert sum(point['holdoutPasses'] for point in attending) == -score
            assert sum(point['paidLookups'] for point in attending) == cost
