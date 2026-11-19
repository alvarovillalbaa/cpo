from itertools import product
import unittest

from benchmarks.starting_prompt_margin import qualify_archive_margin


class StartingPromptMarginTests(unittest.TestCase):
    def test_early_archive_proof_matches_the_full_margin(self):
        rows = range(3)
        for old, new in product(product((False, True), repeat=3), repeat=2):
            for margin in (2, 3):
                with self.subTest(old=old, new=new, margin=margin):
                    calls = []

                    def evaluate(prompt, case):
                        calls.append((prompt, case))
                        return (old if prompt == 'old' else new)[case]

                    passes, charged, _ = qualify_archive_margin('old', 'new', rows, evaluate, margin)
                    self.assertEqual(passes, sum(new) - sum(old) >= margin)
                    self.assertEqual(charged, len(calls) - len(rows))
                    self.assertEqual(len(calls), len(set(calls)))

    def test_does_not_buy_archive_replies_for_an_impossible_margin(self):
        def evaluate(prompt, case):
            self.assertEqual(prompt, 'old')
            return True

        self.assertEqual(qualify_archive_margin('old', 'new', range(3), evaluate, 2), (False, 0, []))
