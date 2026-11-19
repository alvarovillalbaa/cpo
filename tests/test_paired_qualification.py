from collections import Counter
from itertools import product
from random import Random
import unittest

from cpo import Row
from cpo.paired_qualification import certify_paired_qualification


def scheduled(rows, repeats, seed):
    generator = Random(seed)
    for row in rows:
        for repeat in range(repeats):
            prompts = ['old', 'new']
            generator.shuffle(prompts)
            yield from ((prompt, row.id, repeat) for prompt in prompts)


def full_decision(rows, repeats, minimum_gain, evidence):
    gains = Counter()
    for row in rows:
        for repeat in range(repeats):
            old, new = (evidence[prompt, row.id, repeat] for prompt in ('old', 'new'))
            if row.critical and old and not new:
                return 'rejected'
            gains[row.family] += new - old
    return 'promoted' if sum(gains.values()) >= minimum_gain and min(gains.values()) >= 0 else 'rejected'


class PairedQualificationTests(unittest.TestCase):
    def test_stops_at_the_first_decisive_prefix_under_repeats_and_family_constraints(self):
        rows = (Row('risk', 'alpha', True), Row('ordinary', 'beta'))
        repeats, seed = 2, 4
        order = tuple(scheduled(rows, repeats, seed))
        worlds = list(product((False, True), repeat=len(order)))
        for minimum in (1, 2, 4, 5):
            possible = {}
            for bits in worlds:
                outcome = full_decision(rows, repeats, minimum, dict(zip(order, bits, strict=True)))
                for size in range(len(bits) + 1):
                    possible.setdefault(bits[:size], set()).add(outcome)
            for bits in worlds:
                evidence = dict(zip(order, bits, strict=True))
                result = certify_paired_qualification('old', 'new', rows,
                                                      lambda prompt, row, repeat: evidence[prompt, row.id, repeat],
                                                      repeats=repeats, minimum_gain=minimum, seed=seed)
                used = len(result.observations)
                self.assertEqual(possible[bits[:used]], {result.status})
                if used:
                    self.assertEqual(possible[bits[:used - 1]], {'promoted', 'rejected'})
                self.assertEqual([(item.prompt, item.row_id, item.repeat, item.passed) for item in result.observations],
                                 [(*key, value) for key, value in zip(order[:used], bits[:used], strict=True)])

    def test_a_single_reply_can_settle_a_pair_without_a_counterpart(self):
        # Seed zero starts the single pair with the incumbent, which passes.
        result = certify_paired_qualification('old', 'new', [Row('one', 'task')], lambda *_: True)
        self.assertEqual(result.status, 'rejected')
        self.assertEqual(len(result.observations), 1)
        self.assertEqual((result.lower_gain, result.upper_gain), (-1, 0))

    def test_an_exhausted_budget_does_not_imply_rejection(self):
        result = certify_paired_qualification('old', 'new', [Row('one', 'task')], lambda *_: False,
                                              evaluation_limit=1)
        self.assertEqual(result.status, 'undecided')
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.prompt, 'old')

    def test_invalid_outcomes_and_budgets_fail_explicitly(self):
        rows = [Row('one', 'task')]
        with self.assertRaisesRegex(ValueError, 'exact boolean'):
            certify_paired_qualification('old', 'new', rows, lambda *_: 1)
        with self.assertRaisesRegex(ValueError, 'nonnegative integer'):
            certify_paired_qualification('old', 'new', rows, lambda *_: False, evaluation_limit=True)
        with self.assertRaisesRegex(ValueError, 'distinct, nonempty'):
            certify_paired_qualification('old', 'new', rows * 2, lambda *_: False)
