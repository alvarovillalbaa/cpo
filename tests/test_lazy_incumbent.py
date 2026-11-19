from collections import Counter
from itertools import product
import unittest

from benchmarks.prompteval_screen_coverage_rotation import select_covered_finalist
from cpo import Observation, Row
from cpo.lazy_incumbent import select_with_lazy_incumbent


class LazyIncumbentTests(unittest.TestCase):
    def test_late_incumbent_cases_are_unneeded_when_no_challenger_passes_the_witness(self):
        rows = tuple(Row(str(case), 'task') for case in range(6))
        paid = []

        def evaluate(prompt, row):
            paid.append((prompt, row.id))
            return Observation(False, {})

        result = select_with_lazy_incumbent('old', ('new', 'later'), rows, evaluate, metric_limit=18)
        self.assertEqual(result.prompt, 'old')
        self.assertIsNone(result.finalist)
        self.assertEqual(result.evaluations, 3)
        self.assertEqual(paid, [('old', '0'), ('new', '0'), ('later', '0')])

    def test_both_proofs_preserve_the_eager_decision_over_all_small_panels(self):
        rows = (Row('a', 'family-a', True), Row('b', 'family-b'), Row('c', 'family-c'))
        prompts = ('old', 'first', 'second')
        keys = tuple(product(prompts, (row.id for row in rows)))
        for bits in product((False, True), repeat=len(keys)):
            outcomes = dict(zip(keys, bits, strict=True))
            calls = []

            def evaluate(prompt, row):
                calls.append((prompt, row.id))
                return Observation(outcomes[prompt, row.id], {})

            for cap, rotate in product((3, 5, 6, 8), (False, True)):
                calls.clear()
                eager = select_covered_finalist(prompts[0], prompts[1:], rows, evaluate, metric_limit=cap,
                                                rotate=rotate, duel=False, audit=Counter())
                eager_challengers = [lookup for lookup in calls if lookup[0] != prompts[0]]
                for paired_proof in (False, True):
                    calls.clear()
                    lazy = select_with_lazy_incumbent(prompts[0], prompts[1:], rows, evaluate, metric_limit=cap,
                                                     rotate_misses=rotate, paired_proof=paired_proof)
                    self.assertEqual((lazy.prompt, lazy.finalist), (eager.prompt, eager.finalist))
                    self.assertEqual(lazy.evaluations, len(set(calls)))
                    self.assertEqual(lazy.evaluations, len(calls))
                    self.assertLessEqual(lazy.evaluations, cap)
                    if not paired_proof:
                        self.assertLessEqual(lazy.evaluations, eager.evaluations)
                        self.assertEqual([lookup for lookup in calls if lookup[0] != prompts[0]], eager_challengers)
