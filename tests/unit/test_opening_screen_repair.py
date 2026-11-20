from unittest import TestCase

from benchmarks.opening_screen_repair import staged_cycle
from cpo import Observation, ProposalPair, Row


class StagedRepairTests(TestCase):
    def setUp(self):
        self.training = [Row('t0', 'a'), Row('t1', 'a')]
        self.validation = [Row(str(case), 'a', critical=case == 0) for case in range(4)]
        self.qualification = [Row('q0', 'a'), Row('q1', 'a')]
        self.values = {'old': '1000', 'first': '1100', 'sibling': '0000', 'repaired': '1111'}
        self.proposed, self.proof, self.search = [], [], []

    def observe(self, prompt, row):
        self.search.append((prompt, row.id))
        return Observation(row.id.isdigit() and self.values[prompt][int(row.id)] == '1', {})

    def propose(self, parent, samples, history, width):
        self.proposed.append((parent, [row.id for row, _ in samples], history, width))
        return ProposalPair('repaired', 'sibling')

    def qualify(self, prompt, row, repeat):
        self.proof.append((prompt, row.id, repeat))
        return prompt != 'old'

    def run_cycle(self, cap=14):
        return staged_cycle(2)('old', self.training, self.validation, self.qualification, self.observe, self.propose,
                               metric_limit=cap, rounds=6, train_per_round=2, opening_pair=ProposalPair('first', 'sibling'),
                               qualify=self.qualify, seed=9, field_credit=False, repeats=1)

    def test_paid_training_errors_route_only_the_final_nominee_to_qualification(self):
        result = self.run_cycle()
        self.assertEqual(result.prompt, 'repaired')
        self.assertEqual(result.search.evaluations, 14)
        self.assertEqual(len(self.search), len(set(self.search)))
        self.assertEqual(result.search.reflections, 1)
        parent, feedback, history, width = self.proposed[0]
        self.assertEqual((parent, set(feedback), history, width), ('first', {'t0', 't1'}, [], 1))
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'repaired'})

    def test_critical_loss_keeps_the_original_nominee(self):
        self.values['repaired'] = '0111'
        result = self.run_cycle()
        self.assertEqual(result.prompt, 'first')
        self.assertEqual(result.search.events[-1]['status'], 'rejected')
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'first'})

    def test_full_passes_skip_the_repair_round(self):
        self.values['first'] = '1111'
        result = self.run_cycle()
        self.assertEqual(result.prompt, 'first')
        self.assertEqual(result.search.events[-1]['status'], 'validation-complete')
        self.assertEqual(self.proposed, [])
        self.assertTrue(all(case.isdigit() for _, case in self.search))

    def test_unfunded_repair_preserves_the_opening(self):
        result = self.run_cycle(cap=12)
        self.assertEqual(result.prompt, 'first')
        self.assertEqual(result.search.evaluations, 8)
        self.assertEqual(result.search.events[-1]['status'], 'unfunded')
        self.assertEqual(self.proposed, [])
