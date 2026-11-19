import unittest

from benchmarks.four_case_qualification_transfer import CANDIDATE, METHODS, PRIMARY, classify, resample


class FourCaseQualificationTransferTests(unittest.TestCase):
    def test_simultaneous_range_uses_the_stronger_primary_on_every_draw(self):
        plan = {'bootstrapSeed': 1, 'bootstrapDraws': 128}
        case = dict.fromkeys((*METHODS, 'retain-start'), 0)
        case.update({CANDIDATE: 3, PRIMARY[0]: 2, PRIMARY[1]: 5})
        ranges, simultaneous = resample(plan, {'first': {4: case}, 'second': {5: case}})
        self.assertEqual(ranges[PRIMARY[0]], [2, 2])
        self.assertEqual(ranges[PRIMARY[1]], [-4, -4])
        self.assertEqual(simultaneous, [-4, -4])

    def test_primary_requires_savings_against_both_controls(self):
        plan = {'primaryComparison': {'minimumLookupSavingPercent': 10, 'minimumLowerRangePassDifference': 0}}
        totals = {CANDIDATE: {'paidLookups': 90}, PRIMARY[0]: {'paidLookups': 100}, PRIMARY[1]: {'paidLookups': 110}}
        self.assertEqual(classify(plan, totals, [0, 4]), 'passed')
        self.assertEqual(classify(plan, totals, [-2, 4]), 'inconclusive')
        self.assertEqual(classify(plan, totals, [-2, -1]), 'failed')
        totals[PRIMARY[1]]['paidLookups'] = 99
        self.assertEqual(classify(plan, totals, [4, 10]), 'failed')
