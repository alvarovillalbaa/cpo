from unittest import TestCase

from cpo import Observation, ProposalBatch, ProposalPair, Row
from cpo.routed_repair_cycle import run_routed_repair_cycle


class RoutedRepairCycleTests(TestCase):
    def setUp(self):
        self.train = [Row(f't{case}', 'a', fields=2) for case in range(4)]
        self.validation = [Row(str(case), family, critical=case == 0, fields=2)
                           for case, family in enumerate(('a', 'b', 'a', 'a'))]
        self.holdout = [Row('q0', 'a'), Row('q1', 'b')]
        self.scores = {'old': (2, 0, 0, 0), 'opening': (2, 2, 1, 0), 'sibling': (0, 0, 0, 0),
                       'provisional': (2, 2, 1, 1), 'final': (2, 2, 2, 2)}
        self.feature_values = dict(zip(('0', '1', '2', '3', 't0', 't1', 't2', 't3'),
                                       (True, True, 1, 1, True, True, 1, 1), strict=True))
        self.search, self.proposals, self.proof, self.features, self.transforms = [], [], [], [], []

    def evaluate(self, prompt, row):
        self.search.append((prompt, row.id))
        matched = self.scores[prompt][int(row.id)] if row.id.isdigit() else 0
        return Observation(matched == 2, {'case': row.id}, matched)

    def input_features(self, row):
        self.features.append(row.id)
        return {'value': self.feature_values[row.id]}

    def transform(self, prompt):
        self.transforms.append(prompt)
        return f'instructions of {prompt}'

    def propose(self, parent, feedback, history, width):
        self.proposals.append((parent, feedback, history, width))
        if parent == 'opening':
            return ProposalPair('provisional', 'unused')
        return ProposalBatch(('final', 'unused'), exhausted=True)

    def qualify(self, prompt, row, repeat):
        self.proof.append((prompt, row.id, repeat))
        return prompt != 'old'

    def cycle(self, **options):
        settings = dict(input_features=self.input_features, opening_pair=ProposalPair('opening', 'sibling'),
                        diagnostic_prompt=self.transform, metric_limit=20, qualify=self.qualify,
                        seed=7, field_credit=True)
        settings.update(options)
        return run_routed_repair_cycle('old', iter(self.train), iter(self.validation), iter(self.holdout),
                                       self.evaluate, self.propose, **settings)

    def test_routes_features_and_keeps_provisional_parent_out_of_qualification(self):
        outcome = self.cycle()
        self.assertEqual(outcome.prompt, 'final')
        self.assertEqual(outcome.search.evaluations, 20)
        self.assertEqual(outcome.search.reflections, 2)
        self.assertEqual(self.transforms, ['opening', 'provisional'])
        self.assertCountEqual(self.features, self.feature_values.keys())
        self.assertEqual([event['status'] for event in outcome.search.events[-2:]], ['provisional', 'accepted'])
        for (parent, feedback, history, width), expected in zip(self.proposals, ({'t2', 't3'}, {'t0', 't1'})):
            self.assertEqual({row.id for row, _ in feedback}, expected)
            self.assertTrue(all(not reply.passed for _, reply in feedback))
            self.assertEqual((history, width), ([], 1))
            self.assertTrue(all((f'instructions of {parent}', row.id) in self.search for row, _ in feedback))
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'final'})

    def test_unfunded_or_perfect_opening_skips_feature_extraction(self):
        self.assertEqual(self.cycle(metric_limit=12).search.prompt, 'opening')
        self.scores['opening'] = (2, 2, 2, 2)
        self.assertEqual(self.cycle().search.prompt, 'opening')
        self.assertEqual((self.transforms, self.features, self.proposals), ([], [], []))

    def test_tied_repair_is_never_the_final_nominee(self):
        outcome = self.cycle(metric_limit=14)
        self.assertEqual(outcome.search.prompt, 'opening')
        self.assertEqual(outcome.search.events[-1]['status'], 'provisional')
        self.assertEqual(self.transforms, ['opening'])
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'opening'})

    def test_rejects_critical_loss_or_family_regression_even_with_exact_gain(self):
        for scores in ((1, 2, 2, 2), (2, 1, 2, 2)):
            with self.subTest(scores=scores):
                self.scores['final'] = scores
                outcome = self.cycle(qualification_limit=0)
                self.assertEqual(outcome.search.prompt, 'opening')
                self.assertEqual(outcome.search.events[-1]['status'], 'rejected')
                self.assertEqual(self.proof, [])

    def test_rejects_invalid_options_before_dispatch(self):
        for options in ({'input_features': None}, {'max_training_probes': True},
                        {'qualification_limit': -1}, {'diagnostic_prompt': 'raw'}, {'recover_stalls': 1},
                        {'fallback_probe_limit': True}, {'fallback_probe_limit': -1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.cycle(**options)
        self.assertEqual(self.search, [])

    def test_recovers_a_field_plateau_without_qualifying_the_provisional_opening(self):
        self.scores['opening'] = (2, 1, 1, 0)
        self.scores['provisional'] = (2, 2, 1, 0)
        blocked = self.cycle()
        self.assertEqual(blocked.search.prompt, 'old')
        self.assertEqual(self.proposals, [])
        recovered = self.cycle(recover_stalls=True)
        self.assertEqual(recovered.prompt, 'final')
        self.assertEqual(self.transforms, ['opening', 'provisional'])
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'final'})

    def test_field_plateau_rejects_per_row_regressions_before_training(self):
        self.scores['old'] = (2, 0, 1, 0)
        self.scores['opening'] = (2, 1, 0, 1)
        outcome = self.cycle(recover_stalls=True)
        self.assertEqual(outcome.search.prompt, 'old')
        self.assertEqual((self.transforms, self.proposals, self.proof), ([], [], []))

    def test_retry_uses_unused_probes_and_keeps_the_validation_reserve(self):
        evaluate = self.evaluate

        def pass_top_probes(prompt, row):
            if row.id in ('t2', 't3'):
                self.search.append((prompt, row.id))
                return Observation(True, {'case': row.id}, 2)
            return evaluate(prompt, row)

        self.evaluate = pass_top_probes
        self.scores['provisional'] = self.scores['final']
        outcome = self.cycle(recover_stalls=True, metric_limit=16)
        self.assertEqual(outcome.search.prompt, 'provisional')
        self.assertEqual(outcome.search.evaluations, 16)
        self.assertEqual([event['status'] for event in outcome.search.events[-2:]], ['no-training-error', 'accepted'])
        self.assertEqual({row.id for row, _ in self.proposals[0][1]}, {'t0', 't1'})

    def test_fallback_stops_at_first_witness_and_passes_training_only(self):
        evaluate = self.evaluate

        def pass_top_probes(prompt, row):
            if row.id in ('t2', 't3'):
                self.search.append((prompt, row.id))
                return Observation(True, {'case': row.id}, 2)
            return evaluate(prompt, row)

        self.evaluate = pass_top_probes
        self.scores['provisional'] = self.scores['final']
        outcome = self.cycle(fallback_probe_limit=2, metric_limit=16)
        event = outcome.search.events[-1]
        self.assertEqual(event['status'], 'accepted')
        self.assertEqual(len(event['fallbackRows']), 1)
        self.assertIn(event['fallbackRows'][0], ('t0', 't1'))
        self.assertEqual(outcome.search.evaluations, 15)
        self.assertEqual([row.id for row, _ in self.proposals[0][1]], event['probeRows'] + event['fallbackRows'])
        self.assertEqual({prompt for prompt, _, _ in self.proof}, {'old', 'provisional'})

    def test_fallback_preserves_full_validation_reserve(self):
        evaluate = self.evaluate

        def pass_training(prompt, row):
            return Observation(True, {}, 2) if row.id.startswith('t') else evaluate(prompt, row)

        self.evaluate = pass_training
        outcome = self.cycle(fallback_probe_limit=2, metric_limit=14)
        self.assertEqual(outcome.search.evaluations, 10)
        self.assertEqual(outcome.search.events[-1]['status'], 'no-training-error')
        self.assertNotIn('fallbackRows', outcome.search.events[-1])
        self.assertEqual(self.proposals, [])
