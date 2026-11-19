import unittest

from cpo import Observation, ProposalPair, Row, search


class FieldCreditTests(unittest.TestCase):
    def test_field_credit_crosses_a_zero_exact_plateau_with_racing_on(self):
        train = [Row('train', 'typed', fields=3)]
        validation = [Row('v1', 'typed', fields=3), Row('v2', 'typed', fields=3)]
        scores = {'seed': 0, 'partial rule': 2, 'complete rule': 3}
        proposals = {'seed': 'partial rule', 'partial rule': 'complete rule'}

        def evaluate(prompt, row):
            matched = scores[prompt]
            return Observation(matched == row.fields, {}, matched_fields=matched)

        def propose(prompt, *_):
            return [proposals[prompt]]

        options = {'metric_limit': 10, 'rounds': 2, 'train_per_round': 1, 'adaptive': True}
        binary = search('seed', train, validation, evaluate, propose, **options)
        graded = search('seed', train, validation, evaluate, propose, **options, field_credit=True)
        self.assertEqual(binary.prompt, 'seed')
        self.assertEqual(graded.prompt, 'complete rule')
        self.assertLessEqual(graded.evaluations, options['metric_limit'])

    def test_partial_credit_cannot_override_a_critical_exact_pass(self):
        train = [Row('train', 'typed', fields=4)]
        validation = [Row('critical', 'typed', critical=True, fields=2), Row('ordinary', 'typed', fields=4)]
        scores = {'seed': {'train': 0, 'critical': 2, 'ordinary': 0},
                  'higher partial': {'critical': 1, 'ordinary': 3}}

        def evaluate(prompt, row):
            matched = scores[prompt][row.id]
            return Observation(matched == row.fields, {}, matched_fields=matched)

        result = search('seed', train, validation, evaluate, lambda *_: ['higher partial'],
                        metric_limit=8, rounds=2, train_per_round=1, adaptive=True, field_credit=True)
        self.assertEqual(result.prompt, 'seed')
        self.assertEqual(result.events[-1]['kind'], 'critical_regression')

    def test_field_counts_reject_inconsistent_exact_claims(self):
        with self.assertRaisesRegex(ValueError, 'exact-pass decision'):
            search('seed', [Row('train', 'typed', fields=2)], [Row('validation', 'typed', fields=2)],
                   lambda *_: Observation(True, {}, matched_fields=1), lambda *_: (),
                   metric_limit=3, rounds=1, train_per_round=1, field_credit=True)

    def test_precomputed_opening_uses_validation_budget_and_preserves_critical_passes(self):
        train = [Row('training', 'typed', fields=2)]
        validation = [Row('critical', 'typed', critical=True, fields=2), Row('ordinary', 'typed', fields=2)]
        scores = {
            'seed': {'critical': 2, 'ordinary': 0},
            'regression': {'critical': 1, 'ordinary': 2},
            'complete repair': {'critical': 2, 'ordinary': 2},
        }
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            credit = scores[prompt][row.id]
            return Observation(credit == row.fields, {}, matched_fields=credit)

        result = search('seed', train, validation, evaluate, lambda *_: self.fail('No reflection was needed'),
                        metric_limit=5, rounds=1, train_per_round=1, adaptive=True, field_credit=True,
                        opening_pair=ProposalPair('regression', 'complete repair'))
        self.assertEqual(result.prompt, 'complete repair')
        self.assertEqual(result.evaluations, 5)
        self.assertEqual(result.reflections, 0)
        self.assertEqual(result.events[1]['kind'], 'critical_regression')
        self.assertEqual(calls, [('seed', 'critical'), ('seed', 'ordinary'), ('regression', 'critical'),
                                 ('complete repair', 'critical'), ('complete repair', 'ordinary')])

    def test_reflection_after_precomputed_opening_uses_training_feedback(self):
        train = [Row('training', 'typed', fields=2)]
        validation = [Row('v1', 'typed', fields=2), Row('v2', 'typed', fields=2)]
        scores = {'seed': 0, 'partial rule': 1, 'alternative': 0, 'complete rule': 2}

        def evaluate(prompt, row):
            credit = scores[prompt]
            return Observation(credit == row.fields, {'row': row.id}, matched_fields=credit)

        def propose(parent, feedback, *_):
            self.assertEqual(parent, 'partial rule')
            self.assertEqual([observation.feedback for _, observation in feedback], [{'row': 'training'}])
            return ['complete rule']

        result = search('seed', train, validation, evaluate, propose, metric_limit=7, rounds=2,
                        train_per_round=1, adaptive=True, field_credit=True,
                        opening_pair=ProposalPair('partial rule', 'alternative'))
        self.assertEqual((result.prompt, result.evaluations, result.reflections), ('complete rule', 7, 1))


if __name__ == '__main__':
    unittest.main()
