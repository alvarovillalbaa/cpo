from itertools import product
import unittest

from benchmarks.paid_incumbent_credit import paid_search
from cpo import Observation, Row
from cpo.lazy_incumbent import select_with_lazy_incumbent


class PaidIncumbentCreditTests(unittest.TestCase):
    def test_credited_seeded_search_preserves_paid_cap_and_exact_gate(self):
        prompts = ('base', 'first', 'second')
        rows = (Row('0', 'task', True), Row('1', 'task'), Row('2', 'task'))
        keys = [(prompt, row.id) for prompt in prompts for row in rows]
        for scores in product((False, True), repeat=len(keys)):
            outcomes = dict(zip(keys, scores, strict=True))
            for mask, limit in product(product((False, True), repeat=len(rows)), range(3, 8)):
                previous = {key for key, use in zip(keys[:len(rows)], mask, strict=True) if use}
                known = {key: Observation(outcomes[key], {}) for key in previous}
                credit, measure, paid = paid_search(
                    known, prompts[0], rows, lambda p, r: Observation(outcomes[p, r.id], {}),
                    limit=limit, credit=True)
                result = select_with_lazy_incumbent(prompts[0], prompts[1:], rows, measure,
                                                     metric_limit=limit + credit)
                self.assertEqual(credit, len(previous))
                self.assertEqual(paid(), len(known.keys() - previous))
                self.assertLessEqual(paid(), limit)
                if result.prompt != prompts[0]:
                    self.assertGreater(sum(outcomes[result.prompt, row.id] for row in rows),
                                       sum(outcomes[prompts[0], row.id] for row in rows))
                    self.assertTrue(outcomes[result.prompt, '0'] or not outcomes[prompts[0], '0'])
