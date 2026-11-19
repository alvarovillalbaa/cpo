import unittest

from cpo import Observation, Row, search


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


if __name__ == '__main__':
    unittest.main()
