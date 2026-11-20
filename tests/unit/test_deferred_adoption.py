from unittest import TestCase

from benchmarks.deferred_adoption import ApprovedPrompt, best_approved, episode
from benchmarks.prompteval_continuous import schedule


class DeferredAdoptionTests(TestCase):
    def test_prioritize_a_paid_gain_then_fewer_reads_then_recency(self):
        approved = [ApprovedPrompt('old', 1, 10, 0), ApprovedPrompt('short', 1, 9, 1),
                    ApprovedPrompt('recent', 1, 9, 2)]
        self.assertEqual(best_approved([], 'start'), 'start')
        self.assertEqual(best_approved(approved, 'start'), 'recent')
        approved.append(ApprovedPrompt('strong', 2, 13, 0))
        self.assertEqual(best_approved(approved, 'start'), 'strong')

    def test_keep_start_until_banked_candidate_is_reconfirmed(self):
        self.check_episode(reconfirm=True)

    def test_keep_start_until_selecting_from_the_paid_proofs(self):
        self.check_episode(reconfirm=False)

    def check_episode(self, *, reconfirm):
        original = {'cycles': 4, 'qualificationRowsPerCycle': 8, 'minimumQualificationGain': 1,
                    'trainRows': 12, 'validationRows': 24, 'poolSize': 13}
        plan = {'schedule': original, 'validationRows': 12, 'searchCap': 52}
        held = [0, 1]
        start, _ = schedule(128, 64, held, 36, original)
        matrix = ['1' * 128 for _ in range(64)]
        matrix[int(start)] = '0' * 128
        totals, trace = episode(matrix, held, 36, plan, start, reconfirm=reconfirm)
        self.assertTrue(all(row['decision']['selected'] == start for row in trace[:3]))
        self.assertNotEqual(trace[-1]['decision']['selected'], start)
        self.assertEqual(totals['approvedEarly'], 3)
        self.assertEqual(totals['holdoutPasses'], 2)
        self.assertEqual(totals['finalRechecksPassed'], int(reconfirm))
