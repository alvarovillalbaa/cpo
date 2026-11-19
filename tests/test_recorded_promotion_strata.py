import unittest

from benchmarks.recorded_promotion_strata import assign_risk_panels, coverage, risk_stratum


class RiskPanelTests(unittest.TestCase):
    def test_policy_inputs_define_strata_without_expected_answers(self):
        def outage(duration, evidence='MISSING'):
            return risk_stratum('outage', {'id': 'row', 'input': f'Record row. Duration minutes={duration}; '
                                          f'Plan=PLUS; Monthly fee whole USD=40; Evidence={evidence}.'})

        self.assertEqual([outage(i) for i in (29, 30, 119, 120)],
                         [(0, 'MISSING'), (1, 'MISSING'), (1, 'MISSING'), (2, 'MISSING')])
        self.assertEqual(outage(30, 'POSTED'), (1, 'POSTED'))
        with self.assertRaisesRegex(ValueError, 'archived outage input'):
            risk_stratum('outage', {'id': 'row', 'input': 'unrecognized'})

    def test_coverage_increases_with_matched_critical_counts_and_swaps(self):
        validation = ['a', 'b', 'c']
        promotion = ['d', 'e', 'f']
        critical = {'a', 'b', 'd', 'e'}
        strata = {'a': 'boundary', 'b': 'missing', 'c': 'posted',
                  'd': 'missing', 'e': 'missing', 'f': 'posted'}
        layouts = assign_risk_panels(validation, promotion, critical, strata, 42)
        self.assertEqual(layouts, assign_risk_panels(validation, promotion, critical, strata, 42))
        for val, pro in layouts.values():
            self.assertEqual(set(val + pro), set(validation + promotion))
            self.assertEqual((len(val), len(pro)), (3, 3))
            self.assertEqual((len(set(val) & critical), len(set(pro) & critical)), (2, 2))
            self.assertEqual(len(set(pro) - set(promotion)), 1)
        self.assertEqual(coverage(layouts['risk-diverse'][1], critical, strata), (2, 3))

    def test_tie_retains_entire_original_order(self):
        validation = ['v2', 'v1']
        promotion = ['p2', 'p1']
        strata = dict.fromkeys(validation + promotion, 'same')
        layouts = assign_risk_panels(validation, promotion, set(), strata, 0)
        self.assertEqual(layouts, {name: (validation, promotion) for name in ('risk-diverse', 'matched-swaps')})
