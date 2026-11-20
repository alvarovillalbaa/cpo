from collections import Counter
from itertools import product
from unittest import TestCase

from benchmarks.independent_witness_validation import select
from cpo import Observation, Row
from cpo.lazy_incumbent import select_with_lazy_incumbent


class IndependentWitnessValidationTests(TestCase):
    def setUp(self):
        self.rows = tuple(Row(str(index), 'validation', index == 3) for index in range(4))

    def check(self, old, new, cap, *, net_gain):
        replies = {'old': old, 'new': new}
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(replies[prompt][int(row.id)] == '1', {})

        audit = Counter()
        result = select('old', ('new',), self.rows, evaluate, metric_limit=cap, net_gain=net_gain, audit=audit)
        self.assertLessEqual(len(calls), cap)
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(result.evaluations, len(calls))
        return result, calls, audit

    def test_reject_a_gain_confined_to_the_screen(self):
        for net_gain in (False, True):
            result, _, audit = self.check('0011', '1011', 8, net_gain=net_gain)
            self.assertEqual(result.prompt, 'old')
            self.assertEqual(audit['nomineesVetoed'], 1)

    def test_second_repair_can_offset_a_loss(self):
        second_repair, _, _ = self.check('0011', '1101', 8, net_gain=False)
        net_gain, _, _ = self.check('0011', '1101', 8, net_gain=True)
        self.assertEqual(second_repair.prompt, 'new')
        self.assertEqual(net_gain.prompt, 'old')

    def test_exhaustive_complement_decisions_keep_exact_safety_and_cap(self):
        for outcomes in product('01', repeat=8):
            old, new = ''.join(outcomes[:4]), ''.join(outcomes[4:])
            for cap in (7, 8, 9):
                baseline_calls = []

                def evaluate(prompt, row):
                    baseline_calls.append((prompt, row.id))
                    return Observation((old if prompt == 'old' else new)[int(row.id)] == '1', {})

                reference = select_with_lazy_incumbent('old', ('new',), self.rows, evaluate, metric_limit=cap)
                for net_gain in (False, True):
                    result, calls, _ = self.check(old, new, cap, net_gain=net_gain)
                    self.assertEqual(calls[:len(baseline_calls)], baseline_calls)
                    if reference.prompt == 'old':
                        self.assertEqual(result, reference)
                    else:
                        witness = int(next(case for prompt, case in baseline_calls if prompt == 'new'))
                        gains = [int(b) - int(a) for index, (a, b) in enumerate(zip(old, new, strict=True))
                                 if index != witness]
                        accepted = sum(gains) > 0 if net_gain else 1 in gains
                        self.assertEqual(result.prompt, 'new' if accepted else 'old')
                        self.assertEqual(result.finalist, 'new')
