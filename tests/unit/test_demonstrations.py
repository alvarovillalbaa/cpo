import unittest

from benchmarks import joint_demo_bundles as study, typed_policy
from cpo.demonstrations import stratified_demo_bundles


class DemonstrationBundleTests(unittest.TestCase):
    def test_preserves_rare_strata_for_later_bundles(self):
        cases = list(range(10))
        strata = {index: 'rare' if index < 2 else 'common' for index in cases}
        bundles = stratified_demo_bundles(cases, strata, bundle_size=4, bundle_count=2, seed=19)
        self.assertEqual(len({case for bundle in bundles for case in bundle}), 8)
        self.assertTrue(all({strata[case] for case in bundle} == {'rare', 'common'} for bundle in bundles))
        self.assertEqual(bundles, stratified_demo_bundles(cases, strata, bundle_size=4, bundle_count=2, seed=19))

    def test_rejects_unfunded_bundles_and_missing_strata(self):
        with self.assertRaises(ValueError):
            stratified_demo_bundles([0, 1], {0: 'a', 1: 'b'}, bundle_size=2, bundle_count=2)
        with self.assertRaises(ValueError):
            stratified_demo_bundles([0, 1], {0: 'a'}, bundle_size=2, bundle_count=1)

    def test_balanced_grid_keeps_instruction_slots_and_uses_input_strata(self):
        training = typed_policy.cohorts(43103)['outage']['train']
        original = study.risk.parent.candidate_grid('outage', training, 43103)
        balanced = study.balanced_grid('outage', training, 43103, original)
        self.assertEqual([row[0] for row in balanced], [row[0] for row in original])
        self.assertEqual(balanced, study.balanced_grid(
            'outage', [{**row, 'expected': {}} for row in training], 43103, original,
        ))
        decode = study.risk.parent.grounded.load_json
        demos = [decode(program)['demos'] for program in balanced[0]]
        self.assertEqual([len(bundle) for bundle in demos], [0, 4, 4, 4])
        self.assertEqual(len({index for bundle in demos for index in bundle}), 12)
