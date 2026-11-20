from unittest import TestCase

from benchmarks.alternative_controls import encode
from benchmarks.opening_staged_repairs import cycle
from cpo import Observation, ProposalPair, Row


class OpeningStagedRepairsTests(TestCase):
    def run_cycle(self, final_passes, *, validation_probe_limit=0):
        initial, opening, sibling, intermediate_a, intermediate_b, final = map(
            encode, ('initial', 'opening', 'sibling', 'stage a', 'stage b', 'final'))
        train = [Row('t0', 'family', fields=1), Row('t1', 'family', fields=1)]
        validation = [Row(f'v{i}', 'family', critical=i == 0, fields=1) for i in range(3)]
        holdout = [Row('q0', 'family'), Row('q1', 'family')]
        expected = {initial: {'v0'}, sibling: set(), opening: {'v0', 'v1'},
                    intermediate_a: {'v0', 'v1'}, intermediate_b: {'v0', 'v1'}, final: final_passes}
        features = {row.id: {} for row in (*train, *validation)}
        evaluated, qualified, parents = [], [], []
        options = iter((intermediate_a, intermediate_b, final))

        def evaluate(prompt, row):
            evaluated.append((prompt, row.id))
            passed = row.id in expected[prompt] if row.id.startswith('v') else False
            return Observation(passed, {}, int(passed))

        def propose(parent, feedback, history, width):
            parents.append(parent)
            self.assertTrue(all(row.id.startswith('t') for row, _ in feedback))
            self.assertEqual((history, width), ([], 1))
            return next(options)

        def qualify(prompt, row, repeat):
            qualified.append(prompt)
            return prompt != initial

        run = cycle(features, opening_witness_only=bool(validation_probe_limit),
                    validation_probe_limit=validation_probe_limit)
        result = run(initial, train, validation, holdout, evaluate, propose,
                     opening_pair=ProposalPair(opening, sibling), metric_limit=24, qualify=qualify,
                     seed=5, field_credit=True, repeats=1, rounds=6, train_per_round=2)
        self.assertEqual(parents, [opening, intermediate_a, intermediate_b])
        self.assertEqual(result.search.reflections, 3)
        self.assertEqual(result.search.evaluations, len(evaluated))
        self.assertEqual({case for prompt, case in evaluated if prompt == final}, {'v0', 'v1', 'v2'})
        return result, set(qualified), initial, opening, final

    def test_only_the_completed_chain_uses_validation_and_qualification(self):
        result, qualified, initial, _, final = self.run_cycle({'v0', 'v1', 'v2'})
        self.assertEqual(result.search.prompt, final)
        self.assertEqual(qualified, {initial, final})

    def test_complete_chain_cannot_promote_after_critical_regression(self):
        result, qualified, initial, opening, _ = self.run_cycle({'v1', 'v2'})
        self.assertEqual(result.search.prompt, opening)
        self.assertEqual(result.search.events[-1]['status'], 'rejected')
        self.assertEqual(qualified, {initial, opening})

    def test_residual_checks_use_previous_misses_without_exposing_validation_feedback(self):
        result, qualified, initial, _, final = self.run_cycle({'v0', 'v1', 'v2'}, validation_probe_limit=4)
        self.assertEqual(result.search.events[-1]['residualChecks'], [(1, 'v2', False), (2, 'v2', False)])
        self.assertEqual(result.search.prompt, final)
        self.assertEqual(qualified, {initial, final})
