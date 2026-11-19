from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmarks.bounded_discovery_transfer import SOURCES, source_rows, verify_panels


class BoundedDiscoveryTransferTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            'reusedMmluSubjects': ['earlier'],
            'inputSnapshots': {'transfer': {'sha256': 'pinned', 'license': 'MIT', 'panels': 2}},
            'validationRowsAndSearchCap': (12, 52), 'trainRows': 12,
            'cycles': 4, 'qualificationRowsPerCycle': 8,
        }
        self.panel = {
            'phase': 'transfer', 'subject': 'unseen', 'model': 'first', 'correctness': ['0' * 100] * 100,
            'sourceSnapshotSha256': 'pinned', 'license': 'MIT',
            'sourceProvenance': {'caseIDsSha256': 'shared', 'templateIDsSha256': 'templates'},
        }
        self.other = {**self.panel, 'model': 'second'}

    def test_accepts_aligned_panels_with_a_disjoint_schedule(self):
        self.assertEqual(verify_panels([self.panel, self.other], self.plan), {'unseen': 100})

    def test_rejects_reused_subjects_and_misaligned_panel_ids(self):
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            verify_panels([self.panel, {**self.other, 'subject': 'earlier'}], self.plan)
        with self.assertRaisesRegex(ValueError, 'same cases'):
            verify_panels([self.panel, {**self.other, 'sourceProvenance': {'caseIDsSha256': 'different'}}], self.plan)

    def test_capture_checks_exact_source_snapshot_bytes(self):
        with TemporaryDirectory() as scratch:
            path = Path(scratch)
            (path / SOURCES['mmlu'][0]).write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError, 'Archived source bytes differ'):
                next(source_rows(path))
