import unittest

from benchmarks.qualification_role_transfer import first_divergence, qualify_ties, retry_width
from cpo import Row


class QualificationRoleTransferTests(unittest.TestCase):
    def test_shortening_one_archive_role_preserves_the_other_width(self):
        self.assertEqual(retry_width('short-retired', True), 4)
        self.assertEqual(retry_width('short-retired', False), 8)
        self.assertEqual(retry_width('short-rejected', True), 8)
        self.assertEqual(retry_width('short-rejected', False), 4)
        self.assertEqual(retry_width('short-fresh', True), 8)

    def test_audit_distinguishes_archive_gain_and_fresh_gain(self):
        layouts = [{'qualify': list(range(8))}]
        matrix = ['11000000', '10001110']
        old = {'incumbent': '0', 'archiveNominee': None, 'archivePromoted': False, 'challenger': '1', 'selected': '0'}
        selected = dict(old, selected='1')
        expected = {'kind': 'fresh-eight-only', 'fourCaseGain': -1, 'eightCaseGain': 2}
        self.assertEqual(first_divergence(matrix, [{'decision': old}], [{'decision': selected}], layouts), expected)
        old = dict(old, archiveNominee='1', challenger='0')
        selected = dict(selected, archiveNominee='1', archivePromoted=True)
        expected['kind'] = 'archive-eight-only'
        self.assertEqual(first_divergence(matrix, [{'decision': old}], [{'decision': selected}], layouts), expected)

    def test_tie_extension_charges_each_reply_once_and_preserves_the_prefix_sign(self):
        rows = tuple(Row(str(i), 'task') for i in range(8))
        old = '11001100'
        for contender, status, extended in (
                ('10101110', 'promoted', True), ('10101000', 'rejected', True),
                ('10101100', 'rejected', True), ('10001111', 'rejected', False),
                ('11100000', 'promoted', False)):
            for seed in (None, 7):
                calls = []

                def evaluate(prompt, row, repeat):
                    calls.append((prompt, row.id, repeat))
                    return (old if prompt == 'old' else contender)[int(row.id)] == '1'

                decision, used_extra = qualify_ties('old', 'new', rows, evaluate, seed=seed)
                self.assertEqual((decision.status, used_extra), (status, extended))
                self.assertEqual(len(calls), len(set(calls)))
                self.assertEqual(len(calls), len(decision.observations))
                self.assertLessEqual(len(calls), 16 if extended else 8)
