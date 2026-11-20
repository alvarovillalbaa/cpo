from unittest import TestCase

from benchmarks.final_start_reconciliation import reconcile
from benchmarks.prompteval_archive_cycles import qualify_archived
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.paired_qualification import QualificationDecision
from cpo.single_finalist import FinalistResult


class FinalStartReconciliationTests(TestCase):
    def finish(self, selection, *, always, start='111'):
        outcomes = {'start': start, 'incumbent': '100', 'fresh': '110'}
        lookups = []

        def observe(prompt, case):
            lookups.append((prompt, case))
            return outcomes[prompt][case] == '1'

        final, observed = reconcile(selection, 'start', (0, 1, 2), observe, qualify_archived, always=always)
        self.assertEqual(lookups, [(prompt, case) for prompt, case, _ in observed])
        return final, lookups

    def decision(self, status, choice):
        return FixedPoolCycleResult(FinalistResult('fresh', 'fresh', 6),
                                    QualificationDecision(status, choice, (), 0, 2))

    def test_start_faces_the_newly_qualified_prompt(self):
        original = self.decision('promoted', 'fresh')
        final, reads = self.finish(original, always=True)
        self.assertEqual(final.prompt, 'start')
        self.assertEqual({prompt for prompt, _ in reads}, {'start', 'fresh'})
        self.assertIs(final.qualification, original.qualification)

    def test_tie_preserves_the_provisional_choice(self):
        original = self.decision('promoted', 'fresh')
        final, _ = self.finish(original, always=True, start='011')
        self.assertEqual(final.prompt, 'fresh')

    def test_fallback_reads_start_only_after_fresh_rejection(self):
        promoted = self.decision('promoted', 'fresh')
        self.assertEqual(self.finish(promoted, always=False), (promoted, []))
        rejected = self.decision('rejected', 'incumbent')
        final, reads = self.finish(rejected, always=False)
        self.assertEqual(final.prompt, 'start')
        self.assertEqual({prompt for prompt, _ in reads}, {'start', 'incumbent'})
