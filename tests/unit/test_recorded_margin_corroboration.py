from collections import Counter
from itertools import product
import unittest

from benchmarks.recorded_margin_corroboration import POLICIES, qualify_with_support
from cpo import Row


class RecordedMarginCorroborationTests(unittest.TestCase):
    def test_both_orders_match_full_panel_with_critical_and_family_protection(self):
        rows = (Row('0', 'first', True), Row('1', 'first'), Row('2', 'second'), Row('3', 'second'))
        for bits in product((False, True), repeat=8):
            margins = tuple(new - old for old, new in zip(bits[:4], bits[4:], strict=True))
            qualifies = margins[0] >= 0 and sum(margins[:2]) >= 0 and sum(margins[2:]) >= 0
            for training in (False, True):
                for policy in POLICIES:
                    costs, seen, audit = [], set(), Counter()

                    def evaluate(prompt, row, repeat):
                        self.assertEqual(repeat, 0)
                        key = (prompt, row.id)
                        self.assertNotIn(key, seen)
                        seen.add(key)
                        return bits[int(row.id) + 4 * (prompt == 'new')]

                    result = qualify_with_support('old', 'new', rows, evaluate,
                                                  lambda: costs.append('training') or training,
                                                  seed=23, policy=policy, audit=audit)
                    extra = {'training-only': training, 'strength-only': sum(margins) >= 2}.get(
                        policy, training or sum(margins) >= 2)
                    promoted = qualifies and sum(margins) >= 1 and extra
                    self.assertEqual(result.prompt, 'new' if promoted else 'old')
                    self.assertEqual(len(result.observations), len(seen))
                    self.assertLessEqual(len(costs), 1)
                    if not qualifies or sum(margins) < 1:
                        self.assertFalse(costs)

    def test_two_qualification_gains_waive_training(self):
        rows = tuple(Row(str(i), 'task') for i in range(3))
        audit = Counter()
        result = qualify_with_support(
            'old', 'new', rows, lambda prompt, *_: prompt == 'new',
            lambda: self.fail('A second proven gain should waive training'),
            seed=4, policy='strength-first', audit=audit,
        )
        self.assertEqual(result.status, 'promoted')
        self.assertEqual(audit['strengthProved'], 1)

    def test_support_can_be_used_after_an_insufficient_strength_proof(self):
        rows = tuple(Row(str(i), 'task') for i in range(3))
        result = qualify_with_support(
            'old', 'new', rows, lambda prompt, row, _: prompt == 'new' and row.id == '0',
            lambda: True, seed=4, policy='strength-first', audit=Counter(),
        )
        self.assertEqual(result.status, 'promoted')
        self.assertLess(result.upper_gain, 2)
