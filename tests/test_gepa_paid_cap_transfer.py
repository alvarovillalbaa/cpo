import unittest

from benchmarks.gepa_paid_cap_transfer import optimize_by_paid_reads


class GepaPaidCapTests(unittest.TestCase):
    def test_cached_seed_evidence_can_fund_rounds_at_the_same_paid_cap(self):
        incumbent = 'old'
        alternatives = ('first', 'second', 'third', 'fourth', 'fifth', 'sixth')
        train, validation = [0, 1], [2, 3]
        for batched, cap in ((False, 6), (True, 12)):
            for preloaded in (False, True):
                with self.subTest(batched=batched, preloaded=preloaded):
                    cache = ({(prompt, case): False for prompt in (incumbent, *alternatives)
                              for case in (*train, *validation)} if preloaded else {})
                    before = len(cache)

                    def observe(prompt, case):
                        pair = (prompt, case)
                        if pair not in cache:
                            self.assertLess(len(cache) - before, cap)
                            cache[pair] = False
                        return cache[pair]

                    selected, proposals = optimize_by_paid_reads(
                        incumbent, alternatives, train, validation, observe, lambda: len(cache) - before,
                        paid_limit=cap, batched=batched, seed=19,
                    )
                    self.assertEqual(selected, incumbent)
                    if preloaded:
                        self.assertEqual(proposals, len(alternatives))
                        self.assertEqual(len(cache) - before, 0)
                    else:
                        self.assertEqual(proposals, 0)
                        self.assertEqual(len(cache) - before, len(validation))
