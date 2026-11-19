import unittest
from unittest.mock import patch

from benchmarks import prompteval_continuous_budget as budget
from cpo import Observation, Row


class IncumbentBudgetTests(unittest.TestCase):
    def test_incumbent_span_sets_cap_and_search_reuses_paid_observations(self):
        plan = {'targetGain': 2, 'stallRounds': 2, 'incumbentPassFraction': [3, 4],
                'fixedCaps': {}, 'incumbentCaps': {'high': 64, 'low': 112}}
        rows = [Row(str(index), 'task') for index in range(4)]
        for passes, cap in ((3, 64), (2, 112)):
            seen = []
            record = {}

            def observe(prompt, row):
                seen.append((prompt, row.id))
                return Observation(int(row.id) < passes, {})

            def search(initial, _train, validation, evaluate, _propose, **options):
                self.assertEqual(options['metric_limit'], cap)
                self.assertEqual(options['gain_target'], 2)
                self.assertEqual(sum(evaluate(initial, row).passed for row in validation), passes)

            with patch.object(budget.optimizer, 'search', search):
                replay = budget.configure_search(budget.PRIMARY, plan, record)
                replay('base', [], rows, observe, None, metric_limit=171)
            self.assertEqual(len(seen), 4)
            self.assertEqual(record, {'incumbentPasses': passes, 'searchCap': cap})
