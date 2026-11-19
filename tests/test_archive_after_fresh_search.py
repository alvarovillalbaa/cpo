import unittest

from benchmarks.archive_after_fresh_search import certify_archived
from cpo import Row


class ArchiveAfterFreshSearchTests(unittest.TestCase):
    rows = tuple(Row(case, 'task') for case in 'abc')

    def evaluate(self, prompt, row):
        key = (prompt, row.id)
        if key not in self.replies:
            self.calls.append(key)
            self.replies[key] = prompt == 'archived'
        return self.replies[key]

    def setUp(self):
        self.replies = {('incumbent', 'a'): False}
        self.calls = []

    def test_skips_attempt_if_only_the_missing_incumbent_rows_fit(self):
        result = certify_archived('incumbent', 'archived', self.rows, self.replies, self.evaluate, 2)
        self.assertIsNone(result)
        self.assertEqual(self.calls, [])

    def test_reuses_incumbent_reply_and_promotes_at_exact_budget(self):
        result = certify_archived('incumbent', 'archived', self.rows, self.replies, self.evaluate, 3)
        self.assertEqual(result.status, 'promote')
        self.assertEqual(self.calls, [('incumbent', 'b'), ('incumbent', 'c'), ('archived', 'a')])

    def test_insufficient_challenger_evidence_cannot_promote(self):
        self.replies[('incumbent', 'a')] = True
        result = certify_archived('incumbent', 'archived', self.rows, self.replies, self.evaluate, 3)
        self.assertEqual(result.status, 'budget')
        self.assertEqual(self.calls, [('incumbent', 'b'), ('incumbent', 'c')])
