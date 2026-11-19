from collections import Counter
import unittest

from benchmarks.cached_witness_fallback import cycle
from cpo import Observation, Row


class CachedWitnessFallbackTests(unittest.TestCase):
    def run_cycle(self, *, seeded_pass=False, qualified=False, limit=12):
        rows = [Row(case, 'task') for case in ('seeded', 'alternate', 'protected')]
        rows[2] = Row('protected', 'task', critical=True)
        validation = {'inc': {'protected'}, 'alt': {'alternate', 'protected'}}
        if seeded_pass:
            validation['alt'].add('seeded')
        lookups = []
        qualification = []
        history = {'alternate': {'inc': False, 'earlier-a': True, 'earlier-b': True}}
        audit = Counter()

        def evaluate(prompt, row):
            lookups.append((prompt, row.id))
            return Observation(row.id in validation[prompt], {})

        def qualify(prompt, row, repeat):
            qualification.append((prompt, row.id, repeat))
            return qualified and prompt == 'alt'

        result = cycle('inc', ['alt'], rows, [Row('holdback', 'task')], evaluate,
                       history=history, policy='two-pass-16', audit=audit, metric_limit=limit,
                       qualify=qualify, seed=0)
        self.assertEqual(result.search.evaluations, len(lookups))
        self.assertEqual(result.qualification_evaluations, len(qualification))
        self.assertEqual(len(lookups), len(set(lookups)))
        self.assertLessEqual(len(lookups), limit)
        return result, audit

    def test_a_primary_certificate_bypasses_fallback_even_after_qualification_rejects(self):
        result, audit = self.run_cycle(seeded_pass=True)
        self.assertEqual(result.search.prompt, 'alt')
        self.assertEqual(result.qualification.status, 'rejected')
        self.assertEqual(audit['fallbackScreens'], 0)

    def test_rejected_fallback_cannot_become_archive_challenger(self):
        result, audit = self.run_cycle()
        self.assertEqual(result.search.prompt, 'inc')
        self.assertIsNone(result.search.finalist)
        self.assertEqual(result.qualification.status, 'rejected')
        self.assertEqual(audit['fallbackCertificates'], 1)

    def test_qualified_fallback_can_promote_within_paid_cap(self):
        result, audit = self.run_cycle(qualified=True, limit=6)
        self.assertTrue(result.promoted)
        self.assertEqual(result.prompt, 'alt')
        self.assertEqual(audit['fallbackPromotions'], 1)
