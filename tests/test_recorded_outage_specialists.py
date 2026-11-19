import unittest

from benchmarks.recorded_outage_specialists import (compare_provider, reserve_cases, route_scores,
                                                    select_strict_winner)


class OutageSpecialistTests(unittest.TestCase):
    def test_reserve_uses_input_strata_and_leaves_a_retained_case(self):
        risks = {**dict.fromkeys(('m3', 'm2', 'm1'), (2, 'MISSING')),
                 **dict.fromkeys(('p2', 'p1', 'p3'), (2, 'POSTED'))}
        self.assertEqual(reserve_cases(risks), {'long-missing': ['m1', 'm2'], 'long-posted': ['p1', 'p2']})
        risks.pop('p3')
        with self.assertRaisesRegex(ValueError, 'retained case'):
            reserve_cases(risks)

    def test_specialist_must_have_both_reserve_passes_and_strict_gain(self):
        scores = {'old': {'a': True, 'b': False}, 'a-incomplete': {'a': True},
                  'b-full': {'a': True, 'b': True, 'held': False}}
        self.assertEqual(select_strict_winner('old', scores, ['a', 'b']), 'b-full')
        scores['old']['b'] = True
        self.assertIsNone(select_strict_winner('old', scores, ['a', 'b']))

    def test_routing_limits_specialist_scope_and_keeps_missing_replies_unknown(self):
        risks = {'long': (2, 'MISSING'), 'short': (1, 'MISSING')}
        specialists = {(2, 'MISSING'): 'expert'}
        observed = {'expert': {'long': True, 'short': False}}
        routed = route_scores(risks, risks, 'general', specialists, 'expert', 'routed', observed)
        self.assertEqual(routed, {'long': True, 'short': None})
        whole = route_scores(risks, risks, 'general', specialists, 'expert', 'whole', observed)
        self.assertEqual(whole, {'long': True, 'short': False})
        self.assertEqual(compare_provider(routed, whole, dict.fromkeys(risks, True)),
                         {'pairedCases': 1, 'missingPairs': 1, 'passDelta': 0, 'criticalLosses': 0})
