from itertools import product
import unittest

from benchmarks.paired_promotion_evidence import certify, evidence_passes, win_ratio_passes
from cpo import Row


class PairedPromotionEvidenceTests(unittest.TestCase):
    def test_same_net_gain_can_have_different_evidence(self):
        self.assertTrue(evidence_passes(2, 0))
        self.assertFalse(evidence_passes(3, 1))
        self.assertFalse(evidence_passes(4, 2))
        self.assertTrue(evidence_passes(4, 1))
        self.assertFalse(evidence_passes(0, 0))
        self.assertTrue(win_ratio_passes(1, 0))
        self.assertTrue(win_ratio_passes(4, 2))
        self.assertFalse(win_ratio_passes(3, 2))

    def test_early_decision_matches_all_suffixes_and_protects_critical_passes(self):
        rows = (Row('0', 'task', True), Row('1', 'task'), Row('2', 'task'), Row('3', 'task'))
        keys = [(prompt, row.id) for row in rows for prompt in ('base', 'next')]

        def expected(observed, accepts):
            bound = [(observed['base', row.id], observed['next', row.id]) for row in rows]
            wins, losses = bound.count((False, True)), bound.count((True, False))
            return 'promoted' if bound[0] != (True, False) and accepts(wins, losses) else 'rejected'

        for bits in product((False, True), repeat=len(keys)):
            outcomes = dict(zip(keys, bits, strict=True))
            for seed, accepts in product((None, 0, 7), (evidence_passes, win_ratio_passes)):
                decision = certify('base', 'next', rows, lambda p, r, _: outcomes[p, r.id], accepts=accepts, seed=seed)
                self.assertEqual(decision.status, expected(outcomes, accepts))
                observed = {(x.prompt, x.row_id): x.passed for x in decision.observations}
                missing = outcomes.keys() - observed.keys()
                for tail in product((False, True), repeat=len(missing)):
                    self.assertEqual(decision.status, expected(observed | dict(zip(missing, tail, strict=True)), accepts))
