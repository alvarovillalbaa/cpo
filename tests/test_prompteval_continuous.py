import unittest

from benchmarks import prompteval_continuous as continuous


class ContinuousReplayTests(unittest.TestCase):
    def test_schedule_never_reuses_qualification_rows_or_alternatives(self):
        plan = {'poolSize': 13, 'cycles': 4, 'qualificationRowsPerCycle': 8,
                'trainRows': 12, 'validationRows': 24}
        holdout = set(range(30))
        initial, cycles = continuous.schedule(100, 100, holdout, 47101, plan)
        keep = [case for cycle in cycles for case in cycle['qualify']]
        search = {case for cycle in cycles for key in ('train', 'validation') for case in cycle[key]}
        prompts = [initial, *(prompt for cycle in cycles for prompt in cycle['alternatives'])]
        self.assertEqual(len(keep), 32)
        self.assertEqual(len(set(keep)), 32)
        self.assertEqual(len(set(prompts)), 49)
        self.assertTrue(search.isdisjoint(set(keep) | holdout))
        self.assertTrue(holdout.isdisjoint(keep))

    def test_margin_probe_is_charged_before_qualification_and_can_veto(self):
        plan = {'evaluationLookupLimit': 16, 'minimumQualificationGain': 1, 'probeSize': 2}
        layout = {'train': [0, 1], 'validation': [2, 3], 'qualify': [4, 5],
                  'alternatives': ['1', '2'], 'seed': 1}
        matrix = ['111010', '001111', '000000']
        default = continuous.step('cpo-pool-four', matrix, '0', layout, plan)
        guarded = continuous.step('cpo-pool-margin', matrix, '0', layout, plan)
        self.assertEqual(default['selected'], '1')
        self.assertEqual(default['qualificationLookups'], 4)
        self.assertEqual(guarded['selected'], '0')
        self.assertEqual(guarded['qualificationLookups'], 0)
        self.assertEqual(guarded['searchLookups'], default['searchLookups'] + 4)

    def test_public_cycle_receipt_must_pass_qualification_for_promotion(self):
        plan = {'evaluationLookupLimit': 16, 'minimumQualificationGain': 1, 'probeSize': 2}
        layout = {'train': [0, 1], 'validation': [2, 3], 'qualify': [4, 5],
                  'alternatives': ['1', '2'], 'seed': 1}
        step = continuous.step('cpo-cycle', ['001011', '001100', '000000'], '0', layout, plan)
        self.assertEqual(step['challenger'], '1')
        self.assertEqual(step['qualificationLookups'], 4)
        self.assertEqual(step['selected'], '0')
