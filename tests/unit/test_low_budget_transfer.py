"""Tier 1. Pure numeric inputs exercise the fixed comparison policy."""

import unittest

from benchmarks.low_budget_transfer import CANDIDATE, case_resampling, classify_primary


class LowBudgetTransferTests(unittest.TestCase):
    def test_gate_requires_both_measured_savings_and_nonnegative_range(self):
        plan = {'primaryComparison': {'minimumLookupSavingPercent': 10, 'minimumLowerRangePassDifference': 0}}
        control = {'paidLookups': 100}
        self.assertEqual(classify_primary(plan, {'paidLookups': 90}, control, [0, 4]), 'passed')
        self.assertEqual(classify_primary(plan, {'paidLookups': 91}, control, [4, 7]), 'failed')
        self.assertEqual(classify_primary(plan, {'paidLookups': 90}, control, [-3, 7]), 'inconclusive')
        self.assertEqual(classify_primary(plan, {'paidLookups': 90}, control, [-7, -3]), 'failed')

    def test_paired_case_counts_preserve_a_constant_difference(self):
        plan = {'bootstrapSeed': 1, 'bootstrapDraws': 30}
        panels = {'subject': {0: {CANDIDATE: 30, 'control': 29}, 4: {CANDIDATE: 9, 'control': 8}}}
        row = case_resampling(plan, panels, ('control',))['control']
        self.assertEqual(row['interval95PassDifferences'], [2, 2])
        self.assertEqual((row['observedPassDifference'], row['drawsCpoHigher']), (2, 30))
