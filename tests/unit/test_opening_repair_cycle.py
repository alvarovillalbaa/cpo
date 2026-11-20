from unittest import TestCase

from cpo import Observation, ProposalBatch, ProposalPair, Row
from cpo.opening_repair_cycle import run_opening_repair_cycle


class OpeningRepairCycleTests(TestCase):
    def setUp(self):
        self.train = [Row('t0', 'family', fields=1), Row('t1', 'family', fields=1)]
        self.validation = [Row(str(case), 'family', critical=case == 0, fields=1) for case in range(4)]
        self.holdout = [Row('q0', 'family'), Row('q1', 'family')]
        self.known = {'old': '1000', 'opening': '1100', 'sibling': '0000', 'better': '1111'}
        self.search, self.proposals, self.proof, self.transforms = [], [], [], []

    def evaluate(self, prompt, row):
        self.search.append((prompt, row.id))
        passed = self.known[prompt][int(row.id)] == '1' if row.id.isdigit() else prompt == 'opening'
        return Observation(passed, {'case': row.id}, int(passed))

    def transform(self, prompt):
        self.transforms.append(prompt)
        return 'instruction only'

    def propose(self, parent, feedback, history, width):
        self.proposals.append((parent, feedback, history, width))
        return ProposalBatch(('better', 'unfunded alternative'), exhausted=True)

    def qualify(self, prompt, row, repeat):
        self.proof.append((prompt, row.id, repeat))
        return prompt != 'old'

    def cycle(self, **options):
        settings = dict(opening_pair=ProposalPair('opening', 'sibling'), metric_limit=14,
                        diagnostic_prompt=self.transform, qualify=self.qualify, field_credit=True, seed=7)
        settings.update(options)
        return run_opening_repair_cycle('old', iter(self.train), iter(self.validation), iter(self.holdout),
                                        self.evaluate, self.propose, **settings)

    def test_only_training_uses_the_transform_and_only_one_nominee_qualifies(self):
        result = self.cycle()
        self.assertEqual(result.prompt, 'better')
        self.assertEqual(result.search.evaluations, 14)
        self.assertEqual(result.search.reflections, 1)
        self.assertEqual(self.transforms, ['opening'])
        self.assertEqual({prompt for prompt, case in self.search if case.startswith('t')}, {'instruction only'})
        self.assertEqual({prompt for prompt, case in self.search if case.isdigit()}, {'old', 'opening', 'better'})
        parent, feedback, history, width = self.proposals[0]
        self.assertEqual((parent, history, width), ('opening', [], 1))
        self.assertEqual({row.id for row, _ in feedback}, {'t0', 't1'})
        self.assertTrue(all(not reply.passed for _, reply in feedback))
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'better'})

    def test_an_absent_transform_uses_the_complete_opening_on_training(self):
        result = self.cycle(diagnostic_prompt=None)
        self.assertEqual(result.prompt, 'opening')
        self.assertEqual(result.search.events[-1]['status'], 'no-training-error')
        self.assertEqual(self.proposals, [])

    def test_budget_reserves_the_repair_before_transforming_or_reading_training(self):
        result = self.cycle(metric_limit=12)
        self.assertEqual(result.prompt, 'opening')
        self.assertEqual(result.search.events[-1]['status'], 'unfunded')
        self.assertEqual(self.transforms, [])
        self.assertEqual(self.proposals, [])
        self.assertEqual(result.search.evaluations, 8)

    def test_strict_gain_with_a_critical_loss_does_not_replace_the_opening(self):
        self.known['better'] = '0111'
        result = self.cycle()
        self.assertEqual(result.prompt, 'opening')
        self.assertEqual(result.search.events[-1]['status'], 'rejected')
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'opening'})

    def test_zero_qualification_allowance_keeps_the_incumbent_without_dispatch(self):
        result = self.cycle(qualification_limit=0)
        self.assertEqual(result.search.prompt, 'better')
        self.assertEqual(result.qualification.status, 'undecided')
        self.assertEqual(result.prompt, 'old')
        self.assertEqual(self.proof, [])

    def test_invalid_configuration_fails_before_search(self):
        for options in ({'max_training_probes': True}, {'qualification_limit': -1}, {'diagnostic_prompt': 'raw'}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.cycle(**options)
        self.assertEqual(self.search, [])
