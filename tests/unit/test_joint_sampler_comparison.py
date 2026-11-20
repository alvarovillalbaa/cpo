from itertools import product
import unittest

from benchmarks import grounded, typed_policy
from benchmarks.joint_sampler_comparison import candidate_grid, exact_gain, run_arm
from cpo import Observation


class JointSamplerComparisonTests(unittest.TestCase):
    def test_demonstration_bundles_are_shared_and_disjoint(self):
        groups = typed_policy.cohorts(42967)['warehouse']
        grid = candidate_grid('warehouse', groups['train'], 42967)
        bundles = [[grounded.load_json(program)['demos'] for program in row] for row in grid]
        self.assertTrue(all(row == bundles[0] for row in bundles))
        self.assertEqual(bundles[0][0], [])
        self.assertEqual(len({index for bundle in bundles[0][1:] for index in bundle}), 12)
        self.assertEqual(grid, candidate_grid('warehouse', groups['train'], 42967))

    def test_sampler_respects_budget_and_independent_panel(self):
        groups = typed_policy.cohorts(42967)['outage']
        grid = candidate_grid('outage', groups['train'], 42967)
        for method in ('tpe-sampler', 'random-sampler', 'tpe-cpo'):
            result = run_arm('outage', groups, grid, 42967, 48, method)
            self.assertLessEqual(result['evaluations'], 48)
            self.assertLessEqual(result['qualificationLookups'], 2 * len(groups['confirmation']))
            self.assertEqual(set(result['holdout']), {row['id'] for row in groups['holdout']})
            self.assertEqual(result['paidLookups'], result['evaluations'] + result['qualificationLookups'] + 2)
            self.assertEqual(result, run_arm('outage', groups, grid, 42967, 48, method))

    def test_bound_preserves_exact_confirmation_with_a_cached_prefix(self):
        rows = [{'id': str(index), 'critical': index == 0} for index in range(3)]
        for bits in product((False, True), repeat=6):
            baseline, candidate = bits[:3], bits[3:]
            for target in range(sum(baseline), 4):
                journal = {('candidate', '1'): Observation(candidate[1], {})}

                def evaluate(prompt, row):
                    key = (prompt, row['id'])
                    if key not in journal:
                        journal[key] = Observation(candidate[int(row['id'])], {})
                    return journal[key]

                gains = sum(candidate) > target and (not baseline[0] or candidate[0])
                expected = sum(candidate) if gains else None
                self.assertEqual(exact_gain('candidate', rows, baseline, target, evaluate, journal, early=True), expected)
                self.assertLessEqual(len(journal), len(rows))
