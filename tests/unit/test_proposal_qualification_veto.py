from collections import Counter
from itertools import product
from types import SimpleNamespace
from unittest import TestCase

from benchmarks.proposal_qualification_corroboration import corroborate
from benchmarks.proposal_qualification_veto import veto_with_evidence
from cpo import Row
from cpo.paired_qualification import certify_paired_qualification


class ProposalVetoTests(TestCase):
    def setUp(self):
        self.rows = [Row('0', 'task')]
        self.decision = certify_paired_qualification('0', '1', self.rows, lambda prompt, *_: prompt == '1')
        self.result = SimpleNamespace(promoted=True, qualification=self.decision, prompt='1')
        self.decide = veto_with_evidence(corroborate)

    def test_preserve_ties_and_gains_on_the_extra_cases(self):
        for old_first, old_second, new_first, new_second in product('01', repeat=4):
            matrix = ('0' + old_first + old_second, '1' + new_first + new_second)
            gain = int(new_first) + int(new_second) - int(old_first) - int(old_second)
            counters = Counter()
            selection, paid = self.decide(matrix, '0', self.result, self.rows, {'seed': 0, 'corroborate': [1, 2]},
                                          enforce=False, counters=counters)
            self.assertEqual(selection, '0' if gain < 0 else '1', matrix)
            self.assertEqual(counters['vetoed'], int(gain < 0))
            self.assertEqual(len(paid), 4)

    def test_leave_original_promotion_when_no_panel_exists(self):
        selection, paid = self.decide(('0', '1'), '0', self.result, self.rows, {'seed': 0, 'corroborate': []},
                                      enforce=False, counters=Counter())
        self.assertEqual((selection, paid), ('1', []))

    def test_reject_partial_fresh_evidence(self):
        decide = veto_with_evidence(lambda *_args, **_options: ('1', [('1', '1', False)]))
        with self.assertRaisesRegex(ValueError, 'entire fresh paired panel'):
            decide(('000', '111'), '0', self.result, self.rows, {'seed': 0, 'corroborate': [1, 2]},
                   enforce=False, counters=Counter())
