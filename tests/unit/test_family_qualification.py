from collections import Counter
from itertools import product
from unittest import TestCase

from cpo import Row
from cpo.family_qualification import certify_family_qualification


class FamilyQualificationTests(TestCase):
    def test_matches_full_paired_gate_on_all_two_repeat_outcomes(self):
        rows = (Row('a0', 'a', critical=True), Row('b0', 'b'), Row('a1', 'a'))
        keys = tuple((row.id, repeat) for row in rows for repeat in range(2))
        for outcomes in product((False, True), repeat=2 * len(keys)):
            old = dict(zip(keys, outcomes[:len(keys)], strict=True))
            new = dict(zip(keys, outcomes[len(keys):], strict=True))
            gains = Counter()
            critical_loss = False
            for row in rows:
                for repeat in range(2):
                    key = row.id, repeat
                    gains[row.family] += new[key] - old[key]
                    critical_loss |= row.critical and old[key] and not new[key]
            promotes = not critical_loss and min(gains.values()) >= 0 and sum(gains.values()) >= 1

            def evaluate(prompt, row, repeat):
                return (old if prompt == 'old' else new)[row.id, repeat]

            decision = certify_family_qualification('old', 'new', rows, evaluate, repeats=2, seed=3)
            self.assertEqual(decision.prompt, 'new' if promotes else 'old', outcomes)
            keys_read = {(reply.prompt, reply.row_id, reply.repeat) for reply in decision.observations}
            self.assertEqual(len(keys_read), len(decision.observations), outcomes)

    def test_budget_returns_the_observed_prefix(self):
        rows = (Row('a0', 'a', critical=True), Row('b0', 'b'))
        complete = certify_family_qualification('old', 'new', rows, lambda prompt, *_: prompt == 'new', repeats=2)
        for budget in range(len(complete.observations)):
            result = certify_family_qualification('old', 'new', rows, lambda prompt, *_: prompt == 'new',
                                                   repeats=2, evaluation_limit=budget)
            self.assertEqual(result.status, 'undecided')
            self.assertEqual(result.prompt, 'old')
            self.assertEqual(result.observations, complete.observations[:budget])

    def test_requires_a_boolean_reply(self):
        with self.assertRaises(ValueError):
            certify_family_qualification('old', 'new', [Row('a', 'a')], lambda *_: 1)
