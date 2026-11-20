from collections import Counter
from unittest import TestCase
from unittest.mock import patch

from benchmarks.expected_cost_proposal_replay import archive_step
from benchmarks.proposal_opening_rescue import with_rescue
from benchmarks.proposal_short_validation import short_search
from cpo import expected_cost_proposal_cycle as cycle


class OpeningRescueTests(TestCase):
    def setUp(self):
        self.layout = {'alternatives': ['1', '2'], 'train': [8], 'validation': list(range(6)),
                       'qualify': [6, 7], 'seed': 17}
        self.plan = {'evaluationLookupLimit': 18, 'probeSize': 1, 'minimumQualificationGain': 1}

    def run_rescue(self, matrix, *, threshold=None, budget=18):
        counts = Counter()
        screen = short_search(2, counts)
        search = with_rescue(screen, counts, minimum_prefix_gain=threshold, width=2)
        with patch.object(cycle, 'search', search):
            result, _, _ = archive_step(matrix, '0', self.layout, {**self.plan, 'evaluationLookupLimit': budget})
        self.assertLessEqual(result.search.evaluations, budget)
        return result, counts

    def test_qualify_the_sibling_only_after_the_original_nominee_is_rejected(self):
        result, counts = self.run_rescue(['001100000', '110000110', '101100110'])
        self.assertEqual(result.prompt, '2')
        self.assertEqual(counts['fullPanelRejections'], 1)
        self.assertEqual(counts['rescueNominations'], 1)
        self.assertEqual({reply.prompt for reply in result.qualification.observations}, {'0', '2'})

    def test_preserve_the_first_nominee_when_it_passes_full_validation(self):
        result, counts = self.run_rescue(['001100000', '111000110', '101100110'])
        self.assertEqual(result.prompt, '1')
        self.assertEqual(counts['rescueLookups'], 0)

    def test_screen_can_reject_a_sibling_before_its_full_challenge(self):
        matrix = ['101000000', '110000110', '001110110']
        open_result, _ = self.run_rescue(matrix)
        screened, counts = self.run_rescue(matrix, threshold=0)
        self.assertEqual(open_result.prompt, '2')
        self.assertEqual(screened.prompt, '0')
        self.assertEqual(counts['rescuePrefixRejections'], 1)
        self.assertEqual(counts['rescueLookups'], 2)
        self.assertIsNone(screened.qualification)

    def test_insufficient_remaining_budget_cannot_open_a_rescue(self):
        result, counts = self.run_rescue(['001100000', '110000110', '101100110'], budget=17)
        self.assertEqual(result.prompt, '0')
        self.assertEqual(counts['unfundedRescues'], 1)
        self.assertEqual(counts['rescueLookups'], 0)
