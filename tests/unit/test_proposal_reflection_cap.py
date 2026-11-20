from unittest import TestCase
from unittest.mock import patch

from benchmarks.proposal_reflection_cap import bounded_search
from benchmarks.proposal_short_validation import archive_episode
from cpo import ProposalPair
from cpo import expected_cost_proposal_cycle as cycle


class ReflectionCapTests(TestCase):
    def test_opening_remains_available_with_a_zero_reflection_cap(self):
        plan = {'evaluationLookupLimit': 72, 'probeSize': 2, 'minimumQualificationGain': 1}
        layout = {'alternatives': [str(prompt) for prompt in range(1, 7)], 'train': [24, 25],
                  'validation': list(range(24)), 'qualify': [26, 27], 'seed': 29}
        matrix = ['00010000' + '0' * 20] + ['0' * 28] * 6
        outcomes = []
        for limit in (0, 1):
            with patch.object(cycle, 'search', bounded_search(cycle.search, limit)):
                selected, counts, _ = archive_episode(matrix, '0', [layout], plan, width=8)
            self.assertEqual(selected, 0)
            self.assertEqual(counts['reflections'], limit)
            self.assertLessEqual(counts['searchLookups'], 72)
            outcomes.append(counts)
        self.assertEqual(outcomes[0]['screenCandidates'], 2)
        self.assertGreater(outcomes[1]['screenCandidates'], outcomes[0]['screenCandidates'])

    def test_reject_excess_callback_before_it_reaches_the_proposer(self):
        def misbehaving(_initial, _train, _validation, _evaluate, propose, **_options):
            propose()
            propose()

        paid = []
        run = bounded_search(misbehaving, 1)
        with self.assertRaisesRegex(ValueError, 'exceeded its reflection cap'):
            run('0', [], [], self.fail, lambda: paid.append('paid'), rounds=5, opening_pair=ProposalPair('1', '2'))
        self.assertEqual(paid, ['paid'])

    def test_cap_requires_an_explicit_opening(self):
        with self.assertRaisesRegex(ValueError, 'requires the precomputed opening'):
            bounded_search(self.fail, 0)('0', [], [], self.fail, self.fail, rounds=5, opening_pair=None)
