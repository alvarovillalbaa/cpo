from collections import Counter
from itertools import product
import unittest

from benchmarks.prompteval_screen_coverage_rotation import select_covered_finalist
from cpo import Observation, Row
from cpo.single_finalist import select_single_finalist


class CoverageRotationTests(unittest.TestCase):
    def run_policy(self, rows, outcomes, *, cap=12, rotate=False, duel=False):
        paid = []
        audit = Counter()

        def evaluate(prompt, row):
            paid.append((prompt, row.id))
            return Observation(row.id in outcomes[prompt], {})

        candidates = tuple(prompt for prompt in outcomes if prompt != 'old')
        result = select_covered_finalist('old', candidates, rows, evaluate, metric_limit=cap,
                                         rotate=rotate, duel=duel, audit=audit)
        self.assertEqual(len(paid), len(set(paid)))
        self.assertEqual(len(paid), result.evaluations)
        self.assertLessEqual(len(paid), cap)
        return result, paid, audit

    def test_rotation_spreads_single_probes_across_incumbent_misses(self):
        rows = tuple(Row(case, 'task') for case in ('good', 'miss1', 'miss2'))
        outcomes = {'old': {'good'}, 'first': set(), 'second': {'good', 'miss2'}}
        shared, _, _ = self.run_policy(rows, outcomes)
        rotated, paid, audit = self.run_policy(rows, outcomes, rotate=True)
        self.assertEqual(shared.prompt, 'old')
        self.assertEqual(rotated.prompt, 'second')
        self.assertEqual(paid[3:5], [('first', 'miss1'), ('second', 'miss2')])
        self.assertEqual(audit['probesOnOtherMisses'], 1)

    def test_retention_check_prefers_a_challenger_that_preserves_the_critical_case(self):
        rows = (Row('critical', 'task', True), Row('miss1', 'task'), Row('miss2', 'task'))
        outcomes = {'old': {'critical'}, 'first': {'miss1', 'miss2'}, 'second': {'critical', 'miss1'}}
        baseline, _, _ = self.run_policy(rows, outcomes)
        duel, _, audit = self.run_policy(rows, outcomes, duel=True)
        self.assertEqual(baseline.prompt, 'old')
        self.assertEqual(duel.prompt, 'second')
        self.assertEqual(audit['duelChangedNominee'], 1)
        self.assertEqual(audit['certificate.promote'], 1)

    def test_duel_reserves_the_budget_to_finish_its_finalist(self):
        rows = (Row('critical', 'task', True), Row('miss1', 'task'), Row('miss2', 'task'))
        outcomes = {'old': {'critical'}, 'first': {'miss1', 'miss2'}, 'second': {'critical', 'miss1'}}
        result, paid, audit = self.run_policy(rows, outcomes, cap=6, duel=True)
        self.assertEqual(result.prompt, 'old')
        self.assertEqual(audit['certificate.critical_regression'], 1)
        self.assertTrue(all(prompt != 'second' for prompt, _ in paid))

    def test_disabled_changes_match_the_original_first_gain_selector_exhaustively(self):
        rows = (Row('a', 'task', True), Row('b', 'task'), Row('c', 'task'))
        prompts = ('old', 'first', 'second')
        keys = tuple(product(prompts, (row.id for row in rows)))
        for bits in product((False, True), repeat=len(keys)):
            outcomes = dict(zip(keys, bits, strict=True))

            def evaluate(prompt, row):
                return Observation(outcomes[prompt, row.id], {})

            for cap in (3, 5, 8):
                original = select_single_finalist(prompts[0], prompts[1:], rows, evaluate,
                                                   metric_limit=cap, screen='first-gain')
                adapted = select_covered_finalist(prompts[0], prompts[1:], rows, evaluate,
                                                  metric_limit=cap, rotate=False, duel=False, audit=Counter())
                self.assertEqual(original, adapted)
