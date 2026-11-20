from collections import Counter
from unittest import TestCase

from benchmarks.proposal_terminal_completion import complete
from cpo import Observation, Result, Row


class ProposalTerminalCompletionTests(TestCase):
    def setUp(self):
        self.rows = [Row(case, 'task') for case in 'abcd']
        self.events = [{'kind': 'budget', 'prompt': 'challenger', 'passed': ['a'], 'unobserved': ['b', 'c', 'd']}]
        self.result = Result('leader', 5, 0, self.events)
        self.journal = {('leader', 'a'): True, ('leader', 'b'): True,
                        ('leader', 'c'): False, ('leader', 'd'): False, ('challenger', 'a'): True}
        self.calls = []

    def run_policy(self, policy, cap, passes='abcd'):
        def evaluate(prompt, row):
            self.assertNotIn((prompt, row.id), self.journal)
            self.calls.append(row.id)
            return Observation(row.id in passes, {})

        audit = Counter()
        selected = complete(self.result, self.rows, self.journal, evaluate, cap=cap, policy=policy, audit=audit)
        self.assertEqual(selected.evaluations, self.result.evaluations + len(self.calls))
        self.assertLessEqual(selected.evaluations, cap)
        return selected, audit

    def test_certificate_can_promote_without_funding_full_suffix(self):
        original, _ = self.run_policy('finish', 7)
        self.assertEqual(original, self.result)
        certificate, audit = self.run_policy('certificate', 7)
        self.assertEqual(certificate.prompt, 'challenger')
        self.assertEqual(self.calls, ['c', 'd'])
        self.assertEqual(audit['certifiedWhilePartial'], 1)

    def test_finish_can_reverse_the_nomination_under_same_budget(self):
        result, audit = self.run_policy('finish', 8)
        self.assertEqual(result.prompt, 'challenger')
        self.assertEqual(self.calls, ['c', 'd', 'b'])
        self.assertEqual(audit['canFinish'], 1)

    def test_unread_critical_loss_prevents_promotion(self):
        self.rows[1] = Row('b', 'task', critical=True)
        result, _ = self.run_policy('certificate', 8, passes='acd')
        self.assertEqual(result.prompt, 'leader')
        self.assertEqual(self.calls, ['b'])

    def test_previously_paid_reply_is_reused_even_if_terminal_event_omitted_it(self):
        self.journal['challenger', 'b'] = True
        self.result = Result('leader', 6, 0, self.events)
        result, audit = self.run_policy('certificate', 7)
        self.assertEqual(result.prompt, 'challenger')
        self.assertEqual(self.calls, ['c'])
        self.assertEqual(audit['tailLookups'], 1)
