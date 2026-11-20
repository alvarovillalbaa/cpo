from unittest import TestCase

from benchmarks.paid_start_retention import METHODS, record, retention


class PaidStartRetentionTests(TestCase):
    def test_missing_counterpart_is_excluded(self):
        validation = {'start': {0: True, 1: True, 2: True, 3: True},
                      'final': {0: False, 1: False, 2: False, 4: False}}
        selected, evidence = retention('start', 'final', validation, {})
        self.assertEqual(evidence['validationPairs'], 3)
        self.assertEqual(selected, dict.fromkeys(METHODS, 'final'))

    def test_corroboration_requires_positive_qualification_evidence(self):
        validation = {'start': {0: True, 1: True, 2: True, 3: True},
                      'final': {0: False, 1: False, 2: True, 3: True}}
        selected, _ = retention('start', 'final', validation, {})
        self.assertEqual(selected, dict(zip(METHODS, ('start', 'final'), strict=True)))
        qualification = {'start': {4: True}, 'final': {4: False}}
        selected, _ = retention('start', 'final', validation, qualification)
        self.assertEqual(selected, dict.fromkeys(METHODS, 'start'))
        qualification['final'][4] = True
        selected, _ = retention('start', 'final', validation, qualification)
        self.assertEqual(selected, dict(zip(METHODS, ('start', 'final'), strict=True)))

    def test_same_paid_lookup_is_counted_once(self):
        ledger = {}
        record(ledger, 'start', '1', True)
        record(ledger, 'start', 1, True)
        self.assertEqual(ledger, {'start': {1: True}})
        with self.assertRaisesRegex(ValueError, 'deterministic'):
            record(ledger, 'start', 1, False)
