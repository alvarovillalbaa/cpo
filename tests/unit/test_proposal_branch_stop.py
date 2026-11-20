from unittest import TestCase
from unittest.mock import patch

from benchmarks.proposal_branch_stop import staged_search
from cpo import Observation, Result, Row


class ProposalBranchStopTests(TestCase):
    def setUp(self):
        self.train = [Row('train', 'task')]
        self.validation = [Row('a', 'task'), Row('b', 'task')]
        self.calls = []

    def run_search(self, score, offers, first_cap, total_cap):
        def evaluate(prompt, row):
            self.calls.append((prompt, row.id))
            return Observation(score(prompt, row), {})

        result = staged_search('start', self.train, self.validation, evaluate, offers, first_cap=first_cap,
                               total_cap=total_cap, probe_size=1, seed=11, minimum_gain=1)
        self.assertEqual(len(self.calls), len(set(self.calls)))
        self.assertEqual(len(self.calls), len(result[1]))
        self.assertLessEqual(len(self.calls), total_cap)
        return result

    def test_a_funded_improvement_ends_search(self):
        nominee, _, counts = self.run_search(lambda p, _: p == 'complete', ('complete', 'other'), 4, 10)
        self.assertEqual(nominee, 'complete')
        self.assertEqual(counts['earlyStops'], 1)
        self.assertEqual(counts['extensions'], 0)
        self.assertEqual(len(self.calls), 4)

    def test_extension_reuses_prefix_and_can_improve(self):
        nominee, _, counts = self.run_search(lambda p, _: p == 'final', ('first', 'second', 'final', 'other'), 4, 10)
        self.assertEqual(nominee, 'final')
        self.assertGreater(counts['cachedEvaluations'], 0)
        self.assertEqual(counts['extensionNomineeChanges'], 1)
        self.assertEqual(counts['reflections'], 1)

    def test_disjoint_expansion_cannot_spend_past_union_cap(self):
        def search(incumbent, train, validation, evaluate, propose, *, metric_limit, **options):
            for row in validation:
                evaluate(incumbent, row)
            for row in validation:
                evaluate('first' if metric_limit == 4 else 'second', row)
            return Result(incumbent, 4, 0, [])

        with patch('benchmarks.proposal_branch_stop.search', side_effect=search):
            nominee, _, counts = self.run_search(lambda *_: False, ('first', 'second'), 4, 5)
        self.assertEqual(nominee, 'start')
        self.assertEqual(counts['firstNomineeRetainedAtCap'], 1)
        self.assertEqual(len(self.calls), 5)
