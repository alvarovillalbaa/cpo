from collections import Counter
from unittest import TestCase
from unittest.mock import patch

from benchmarks.expected_cost_proposal_replay import archive_step
from benchmarks.proposal_opening_pool import opening_pool
from cpo import expected_cost_proposal_cycle as cycle


class OpeningPoolTests(TestCase):
    def setUp(self):
        self.layout = {'alternatives': ['1', '2'], 'train': [6], 'validation': [0, 1, 2, 3],
                       'qualify': [4, 5], 'seed': 17}
        self.plan = {'evaluationLookupLimit': 12, 'probeSize': 1, 'minimumQualificationGain': 1}

    def run_pool(self, matrix, policy, *, plan=None):
        counts = Counter()
        with patch.object(cycle, 'search', opening_pool(policy, counts, screen_rows=2)):
            result, _, _ = archive_step(matrix, '0', self.layout, self.plan if plan is None else plan)
        return result, counts

    def test_fallback_qualifies_only_the_second_when_the_first_ties_full_validation(self):
        result, counts = self.run_pool(['0011000', '1100110', '1011110'], 'opening-fallback')
        self.assertEqual(result.prompt, '2')
        self.assertEqual(result.search.reflections, 0)
        self.assertLessEqual(result.search.evaluations, 12)
        self.assertEqual(counts['twoEligible'], 1)
        self.assertEqual({reply.prompt for reply in result.qualification.observations}, {'0', '2'})

    def test_compare_both_for_the_best_exact_validation_score(self):
        matrix = ['0001000', '1100110', '1011110']
        screened, _ = self.run_pool(matrix, 'opening-screened')
        first, _ = self.run_pool(matrix, 'opening-fallback')
        self.assertEqual(screened.prompt, '2')
        self.assertEqual(first.prompt, '1')

    def test_reject_a_budget_that_cannot_fund_both_exact_challenges(self):
        with self.assertRaisesRegex(ValueError, 'funded pair'):
            self.run_pool(['0000000'] * 3, 'opening-all', plan={**self.plan, 'evaluationLookupLimit': 11})
