"""Tier 1. Exhaustive binary inputs with a pure evaluator callback."""

from itertools import product
import unittest

from benchmarks.paired_archive_preflight import qualify_archive_pair


class PairedArchivePreflightTests(unittest.TestCase):
    def test_exact_archive_decisions_and_challenger_debits(self):
        cases = range(4)
        outcomes = tuple(product((False, True), repeat=4))
        for incumbent, challenger in product(outcomes, repeat=2):
            reads = []

            def evaluate(prompt, case):
                outcome = (incumbent if prompt == 'old' else challenger)[case]
                reads.append((prompt, case, outcome))
                return outcome

            accepted, debit, evidence = qualify_archive_pair('old', 'new', cases, evaluate)
            self.assertEqual(accepted, sum(challenger) > sum(incumbent))
            self.assertEqual(reads, evidence)
            self.assertEqual(debit, sum(prompt == 'new' for prompt, _, _ in reads))
            self.assertEqual(len(reads), len({(prompt, case) for prompt, case, _ in reads}))
