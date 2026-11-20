from unittest import TestCase

from benchmarks.witness_validation_cost_frontier import RETAIN, compare, highest_scoring


class WitnessValidationCostFrontierTests(TestCase):
    def setUp(self):
        cases = {'cpo': (1, 2), 'a': (2, 0), 'b': (0, 2), 'expensive': (4, 4), RETAIN: (1, 0)}
        self.subjects = {'subject': cases}
        costs = {'cpo': 10, 'a': 10, 'b': 9, 'expensive': 12, RETAIN: 0}
        self.totals = {name: {'paidLookups': cost, 'holdoutPasses': sum(cases[name])}
                       for name, cost in costs.items()}

    def test_exclude_unaffordable_results_and_keep_score_match(self):
        groups = {'either': ('a', 'b', 'expensive'), 'expensive-only': ('expensive',)}
        results = compare(self.totals, self.subjects, policies=('cpo',), draws=20, seed=33, groups=groups)['cpo']
        self.assertEqual(results['either']['bestWithinCost'], 'b')
        self.assertEqual(results['either']['holdoutPassDifference'], 1)
        self.assertEqual(results['either']['cheapestMatching'], 'expensive')
        self.assertEqual(results['expensive-only']['bestWithinCost'], RETAIN)
        self.assertNotIn('expensive', results['either']['resampledChoices'])

    def test_reselect_control_in_paired_case_resamples(self):
        result = compare(self.totals, self.subjects, policies=('cpo',), draws=64, seed=62,
                         groups={'either': ('a', 'b')})['cpo']['either']
        self.assertEqual(result['pairedRange95'], [-2, 1])
        self.assertEqual(set(result['resampledChoices']), {'a', 'b'})
        self.assertEqual(sum(result['resampledChoices'].values()), 64)
        self.assertIsNone(result['cheapestMatching'])

    def test_tie_breaks_by_cost_and_then_label(self):
        scores = {'a': 5, 'b': 5, 'c': 5}
        costs = {'a': 4, 'b': 2, 'c': 2}
        self.assertEqual(highest_scoring(costs, scores, ('c', 'b', 'a')), 'b')
