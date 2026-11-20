from collections import Counter
from types import SimpleNamespace
from unittest import TestCase

from benchmarks.proposal_gap_audit import add, classify


class ProposalGapAuditTests(TestCase):
    def setUp(self):
        self.layout = {'alternatives': ['1'], 'validation': [0], 'qualify': [1]}
        self.gepa = {'selected': '1', 'incumbent': '2'}

    def compare(self, matrix, events=(), offered=(), nominee='0'):
        result = SimpleNamespace(prompt='0', search=SimpleNamespace(prompt=nominee, events=events))
        return classify(matrix, self.layout, 1, '0', result, self.gepa, offered)

    def test_compare_qualification_against_cpo_incumbent(self):
        self.assertEqual(self.compare(['01', '11', '00']), 'fails-cpo-pair-qualification')
        self.assertEqual(self.compare(['10', '11', '00']), 'ties-cpo-incumbent-validation')

    def test_distinguish_unoffered_unopened_and_partially_scored(self):
        matrix = ['00', '11', '00']
        self.assertEqual(self.compare(matrix), 'strict-gain-unoffered')
        self.assertEqual(self.compare(matrix, offered={'1'}), 'strict-gain-offered-unopened')
        events = [{'prompt': '1', 'kind': 'budget'}]
        self.assertEqual(self.compare(matrix, events, {'1'}), 'strict-gain-budget')

    def test_shared_nominee_cannot_pass_the_same_exact_gate_and_lose(self):
        with self.assertRaises(ValueError):
            self.compare(['00', '11', '00'], nominee='1')

    def test_signed_gap_can_close_after_incumbents_diverge(self):
        bucket = Counter()
        add(bucket, 3, True)
        add(bucket, -2, False)
        self.assertEqual(bucket, {'cycles': 2, 'positivePassDelta': 3, 'negativePassDelta': -2,
                                  'netPassDelta': 1, 'sharedIncumbentCycles': 1, 'sharedIncumbentPassDelta': 3})
