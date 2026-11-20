from unittest import TestCase
from unittest.mock import patch

from cpo import Observation, ProposalPair, Row, run_cycle
from cpo.expected_cost_proposal_cycle import certify_expected_qualification, run_expected_cost_proposal_cycle
from cpo.paired_qualification import certify_paired_qualification


class ExpectedCostProposalCycleTests(TestCase):
    def setUp(self):
        self.train = [Row('training', 'training', fields=2)]
        self.validation = [Row(f'v{i}', 'validation', fields=2) for i in range(3)]
        self.holdout = [Row(f'q{i}', str(i // 4)) for i in range(8)]
        self.proposals = []
        self.lookups = []

    def evaluate(self, prompt, row):
        self.lookups.append((prompt, row.id))
        complete = prompt == 'complete'
        return Observation(complete, {'seen': row.id}, 2 if complete else 1)

    def propose(self, parent, feedback, history, width):
        self.proposals.append((parent, feedback, history, width))
        return ProposalPair('complete', 'repair')

    def qualify(self, prompt, row, repeat):
        return prompt == 'complete'

    def cycle(self, operation=run_expected_cost_proposal_cycle, qualify=None, **options):
        return operation('start', iter(self.train), iter(self.validation), iter(self.holdout), self.evaluate,
                         self.propose, metric_limit=20, rounds=2, train_per_round=1, field_credit=True,
                         qualify=self.qualify if qualify is None else qualify, **options)

    def test_preserve_search_and_exclude_training_from_qualification_estimate(self):
        baseline = self.cycle(run_cycle)
        observed = self.lookups[:]
        training = self.proposals[:]
        self.lookups.clear()
        self.proposals.clear()
        with patch('cpo.expected_cost_proposal_cycle.certify_expected_qualification',
                   wraps=certify_expected_qualification) as certify:
            ordered = self.cycle()
        self.assertEqual(ordered.search, baseline.search)
        self.assertEqual(ordered.prompt, baseline.prompt)
        self.assertEqual(self.lookups, observed)
        self.assertEqual(self.proposals, training)
        self.assertEqual(certify.call_args.kwargs['validation_counts'], ((0, 3), (3, 3)))
        self.assertLess(ordered.qualification_evaluations, baseline.qualification_evaluations)
        self.assertEqual([row.id for row, _ in training[0][1]], ['training'])

    def test_partial_cap_uses_seeded_prefix(self):
        for limit in (0, 1, 7, 15):
            with self.subTest(limit=limit):
                result = self.cycle(seed=67, qualification_limit=limit)
                seeded = certify_paired_qualification('start', 'complete', self.holdout, self.qualify,
                                                      seed=67, evaluation_limit=limit)
                self.assertEqual(result.qualification, seeded)
                self.assertLessEqual(result.qualification_evaluations, limit)

    def test_opening_skips_proposer_and_repeated_critical_loss_keeps_incumbent(self):
        def qualify(prompt, row, repeat):
            return prompt == 'start' and row.critical or prompt == 'complete' and not row.critical

        self.holdout[0] = Row('q0', '0', critical=True)
        result = self.cycle(qualify=qualify, repeats=2, opening_pair=ProposalPair('complete', 'repair'))
        self.assertEqual(self.proposals, [])
        self.assertEqual(result.search.reflections, 0)
        self.assertEqual(result.prompt, 'start')
        self.assertFalse(result.promoted)

    def test_no_nominee_needs_no_qualification(self):
        self.propose = lambda *_: ['start']
        result = self.cycle(qualify=lambda *_: self.fail('No qualification dispatch belongs here'))
        self.assertIsNone(result.qualification)
        self.assertEqual(result.qualification_evaluations, 0)

    def test_disjointness_and_cap_fail_before_evaluation(self):
        with self.assertRaisesRegex(ValueError, 'nonnegative integer'):
            self.cycle(qualification_limit=False)
        self.holdout = self.train
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            self.cycle()
        self.assertEqual(self.lookups, [])
        self.assertEqual(self.proposals, [])
