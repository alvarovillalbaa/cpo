import unittest

from benchmarks.routed_finalist_model_transfer import CANDIDATE, METHODS, PRIMARY, resample, verdict


class RoutedFinalistTransferTests(unittest.TestCase):
    def test_joint_range_uses_the_worse_of_both_controls(self):
        plan = {'bootstrapSeed': 41, 'bootstrapDraws': 128, 'primaryComparison': {'controls': PRIMARY}}
        deltas = {label: [2] for label in METHODS if label != CANDIDATE}
        deltas[PRIMARY[1]] = [-3]
        ranges, joint = resample(plan, {'subject': deltas})
        self.assertEqual(ranges[PRIMARY[0]], [2, 2])
        self.assertEqual(joint, [-3, -3])

    def test_statistical_range_cannot_override_the_paid_cost_gate(self):
        plan = {'primaryComparison': {'controls': PRIMARY, 'minimumLookupSavingPercent': 10,
                                      'minimumLowerRangePassDifference': 0}}
        totals = {CANDIDATE: {'paidLookups': 90}, PRIMARY[0]: {'paidLookups': 100}, PRIMARY[1]: {'paidLookups': 120}}
        self.assertEqual(verdict(plan, totals, [0, 14]), 'passed')
        self.assertEqual(verdict(plan, totals, [-2, 14]), 'inconclusive')
        totals[PRIMARY[0]]['paidLookups'] = 99
        self.assertEqual(verdict(plan, totals, [0, 14]), 'failed')
