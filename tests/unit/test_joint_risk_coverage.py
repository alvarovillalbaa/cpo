import unittest

from benchmarks import typed_policy
from benchmarks.joint_risk_coverage import covers_strata, critical_groups, diverse_prefix, stratum
from cpo import Observation


class JointRiskCoverageTests(unittest.TestCase):
    def test_outage_prefix_covers_two_distinct_missing_evidence_conditions(self):
        original = typed_policy.cohorts(42709)['outage']['validation']
        reordered = diverse_prefix('outage', original, 3)
        self.assertEqual(len(reordered), len(original))
        self.assertEqual(set(row['id'] for row in reordered), set(row['id'] for row in original))
        self.assertEqual(reordered[0], original[0])
        self.assertEqual([row['critical'] for row in reordered[:3]], [row['critical'] for row in original[:3]])
        self.assertEqual({stratum('outage', row) for row in reordered[1:3]},
                         {('MISSING', 'short'), ('MISSING', 'long')})

    def test_coverage_requires_a_validated_pass_in_each_group(self):
        validation = typed_policy.cohorts(42709)['outage']['validation']
        groups = critical_groups('outage', validation)
        journal = {('candidate', row['id']): Observation(False, {}) for row in validation}
        self.assertFalse(covers_strata('candidate', groups, journal))
        for key, rows in groups.items():
            if key != ('MISSING', 'short'):
                journal['candidate', rows[0]['id']] = Observation(True, {})
        self.assertFalse(covers_strata('candidate', groups, journal))
        journal['candidate', groups['MISSING', 'short'][0]['id']] = Observation(True, {})
        self.assertTrue(covers_strata('candidate', groups, journal))
