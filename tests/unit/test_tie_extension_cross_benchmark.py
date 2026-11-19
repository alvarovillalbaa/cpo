import unittest

from benchmarks.tie_extension_cross_benchmark import CANDIDATE, GEPA, METHODS, resample, verdict


class TieExtensionCrossBenchmarkTests(unittest.TestCase):
    def test_reused_gepa_gate_counts_as_a_primary_control(self):
        plan = {'primaryComparison': {'controls': list(GEPA), 'minimumLookupSavingPercent': 10,
                                      'minimumLowerRangePassDifference': 0}}
        totals = {CANDIDATE: {'paidLookups': 90}, **{key: {'paidLookups': 100} for key in GEPA}}
        self.assertEqual(verdict(plan, totals, [0, 5]), 'passed')
        self.assertEqual(verdict(plan, totals, [-2, 5]), 'inconclusive')
        self.assertEqual(verdict(plan, totals, [-6, -1]), 'failed')
        totals['gepa-batched-ties']['paidLookups'] = 99
        self.assertEqual(verdict(plan, totals, [0, 5]), 'failed')

    def test_joint_case_range_uses_the_minimum_paired_difference(self):
        settings = {'bootstrapSeed': 17, 'bootstrapDraws': 128, 'primaryComparison': {'controls': list(GEPA)}}
        subject = {label: [3] for label in METHODS if label != CANDIDATE}
        subject['gepa-batched-ties'] = [-2]
        ranges, joint = resample(settings, {'first': subject, 'second': subject})
        self.assertEqual(ranges['gepa-batched-eight'], [6, 6])
        self.assertEqual(joint, [-4, -4])
