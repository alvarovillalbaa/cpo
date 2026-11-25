from itertools import product
from random import Random
from unittest import TestCase

from benchmarks import certified_strict_gain_transfer as study


class StrictGainTransferTests(TestCase):
    def test_pooled_selection_matches_exhaustive_pairs(self):
        rng = Random(30)
        for _ in range(30):
            left, right = ({'retain': (rng.randrange(10), 0),
                            **{str(index): (rng.randrange(10), rng.randrange(7)) for index in range(5)}}
                           for _ in range(2))
            for budget in range(13):
                expected = min(
                    (-a[0] - b[0], a[1] + b[1], (name_a, name_b))
                    for (name_a, a), (name_b, b) in product(left.items(), right.items())
                    if a[1] + b[1] <= budget
                )
                score, cost, names = study.most_affordable_passes(budget, left, right)
                self.assertEqual((-score, cost, names), expected)

    def test_pooled_bootstrap_can_concentrate_budget_on_one_task(self):
        plan = {'seeds': (1,), 'tasks': ('left', 'right'), 'draws': 128, 'resampleSeed': 2}
        before = {'candidate': {'paidLookups': 1}, 'retain': {'paidLookups': 0}, 'search': {'paidLookups': 2}}
        left = before, {'candidate': [1, 0], 'retain': [0, 0], 'search': [1, 1]}
        right = before, {'candidate': [0, 1], 'retain': [0, 0], 'search': [1, 0]}
        result = study.pooled_task_controls(plan, (left, right), 'candidate', ('retain', 'search'))
        self.assertEqual(result['controlByTask'], {'left': 'search', 'right': 'retain'})
        self.assertEqual(result['controlPaidLookups'], 2)
        self.assertEqual(result['passDelta'], 0)
        self.assertEqual(sum(result['resampledPairs'].values()), 128)

    def test_qualification_audit_follows_the_deployed_incumbent(self):
        start = study.transfer.donor.START
        windows = [(('first', 'backup'), (), (), (0, 1)),
                   (('second',), (), (), (2, 3))]
        decisions = [('uniform', 'first', 'first'), ('uniform', 'second', 'second')]
        grades = {start: '0000', 'first': '1001', 'second': '0011'}
        study.verify_deployment(grades, windows, decisions)
        grades['second'] = '0001'
        with self.assertRaisesRegex(ValueError, 'strict gain'):
            study.verify_deployment(grades, windows, decisions)
