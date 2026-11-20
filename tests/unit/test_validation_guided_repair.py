from unittest import TestCase

from cpo import Observation, ProposalPair, Row
from cpo.validation_guided_repair import run_validation_guided_repair_cycle


class ValidationGuidedRepairTests(TestCase):
    def test_validates_the_chain_and_honors_a_zero_qualification_allowance(self):
        train = [Row('t0', 'a'), Row('t1', 'a')]
        validation = [Row('v0', 'a', critical=True), Row('v1', 'a'), Row('v2', 'a')]
        holdout = [Row('q0', 'a')]
        prompts = {'old': {'v0'}, 'opening': {'v0', 'v1'}, 'other': set(),
                   'first': {'v0', 'v1'}, 'second': {'v0', 'v1'}, 'third': {'v0', 'v1', 'v2'}}
        edits = iter(('first', 'second', 'third'))
        calls, feedback, features = [], [], []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(row.id in prompts[prompt], {})

        def propose(parent, observed, *_):
            feedback.append((parent, [row.id for row, _ in observed]))
            return next(edits)

        def input_features(row):
            features.append(row.id)
            return {}

        def qualify(*_):
            self.fail('The qualification allowance forbids dispatch')

        result = run_validation_guided_repair_cycle(
            'old', train, validation, holdout, evaluate, propose, input_features=input_features,
            opening_pair=ProposalPair('opening', 'other'), metric_limit=20, qualify=qualify,
            qualification_limit=0,
        )
        self.assertEqual(result.search.prompt, 'third')
        self.assertEqual(result.search.reflections, 3)
        self.assertEqual(result.search.evaluations, len(calls))
        self.assertLessEqual(len(calls), 20)
        self.assertEqual(result.prompt, 'old')
        self.assertNotIn('q0', features)
        self.assertEqual([parent for parent, _ in feedback], ['opening', 'first', 'second'])
        self.assertTrue(all(case.startswith('t') for _, rows in feedback for case in rows))
        self.assertEqual(result.search.events[-1]['residualChecks'], [(1, 'v2', False), (2, 'v2', False)])

    def test_retries_uncovered_training_when_the_first_routed_probes_pass(self):
        train = [Row(f't{i}', 'a') for i in range(5)]
        validation = [Row('v0', 'a', critical=True), Row('v1', 'a'), Row('v2', 'a')]
        holdout = [Row('q0', 'a')]
        prompts = {'old': {'v0'}, 'other': set(), 'opening': {'v0', 'v1'},
                   'first': {'v0', 'v1', 't0', 't1', 't2', 't3'}, 'second': {'v0', 'v1', 'v2'}}
        same_scope = {'v2', 't0', 't1', 't2', 't3'}

        def cycle(retry, metric_limit=20):
            edits = iter(('first', 'second'))
            return run_validation_guided_repair_cycle(
                'old', train, validation, holdout, lambda prompt, row: Observation(row.id in prompts[prompt], {}),
                lambda *_: next(edits), input_features=lambda row: {'scope': row.id in same_scope},
                opening_pair=ProposalPair('opening', 'other'), metric_limit=metric_limit,
                qualify=lambda prompt, *_: prompt != 'old', retry_probe_limit=retry,
            )

        without_retry = cycle(0)
        self.assertEqual(without_retry.search.prompt, 'opening')
        with_retry = cycle(1)
        self.assertEqual(with_retry.prompt, 'second')
        self.assertEqual(with_retry.search.reflections, 2)
        self.assertEqual(with_retry.search.events[-1]['stages'][1]['retryRows'], ['t4'])
        self.assertEqual(with_retry.search.events[-1]['stages'][1]['failedRows'], ['t4'])
        no_spare = cycle(1, metric_limit=without_retry.search.evaluations + 1)
        self.assertLessEqual(no_spare.search.evaluations, without_retry.search.evaluations + 1)
        self.assertEqual(no_spare.search.prompt, 'opening')
