from itertools import product
import unittest

from benchmarks.prompteval_archive_cycles import combine_qualification, nominate, qualify_archived


class ArchiveCycleTests(unittest.TestCase):
    def test_only_the_runner_up_policy_considers_a_rejected_challenger(self):
        history = [{'incumbent': 'past', 'selected': 'current', 'challenger': 'current'},
                   {'incumbent': 'current', 'selected': 'current', 'challenger': 'rejected'}]
        self.assertEqual(nominate('current', history, set(), 'retired'), 'past')
        self.assertEqual(nominate('current', history, set(), 'runner-up'), 'rejected')
        self.assertEqual(nominate('current', history, {('current', 'rejected')}, 'runner-up'), 'past')
        self.assertIsNone(nominate('current', history, {('current', 'rejected'), ('current', 'past')}, 'runner-up'))

    def test_archive_certificate_matches_full_exact_promotion(self):
        cohort = (0, 1, 2)
        for a, b in product(product((False, True), repeat=3), repeat=2):
            scores = {'old': a, 'archive': b}
            promoted, challenger_calls, evidence = qualify_archived('old', 'archive', cohort,
                                                                      lambda prompt, case: scores[prompt][case])
            self.assertEqual(promoted, sum(b) > sum(a))
            self.assertEqual(len(evidence), len(cohort) + challenger_calls)
            self.assertEqual(len({(prompt, case) for prompt, case, _ in evidence}), len(evidence))

    def test_cached_qualification_pairs_are_counted_once(self):
        early = [('old', 5, True), ('retired', 5, False)]
        later = [('old', 5, True), ('new', 5, True)]
        self.assertEqual(combine_qualification(early, later), early + [('new', 5, True)])
        with self.assertRaisesRegex(ValueError, 'contradictory outcomes'):
            combine_qualification(early, [('old', 5, False)])
