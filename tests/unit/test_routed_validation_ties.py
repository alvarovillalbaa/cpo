from itertools import product
import unittest

from benchmarks.routed_validation_ties import certified_tie
from cpo import Observation, Row


class RoutedValidationTieTests(unittest.TestCase):
    def test_bounded_tie_proof_matches_every_binary_panel_and_paid_prefix(self):
        rows = tuple(Row(str(i), 'validation', critical=i == 1) for i in range(3))
        for outcomes in product((False, True), repeat=6):
            old, challenger = outcomes[:3], outcomes[3:]
            for mask, extra in product(range(8), (0, 1, 3)):
                known = [i for i in range(3) if mask & (1 << i)]
                initial = {('old', row.id): Observation(old[i], {}) for i, row in enumerate(rows)}
                initial.update({('new', rows[i].id): Observation(challenger[i], {}) for i in known})
                ledger = initial.copy()

                def observe(prompt, row):
                    key = (prompt, row.id)
                    self.assertNotIn(key, ledger)
                    value = Observation(challenger[int(row.id)], {})
                    ledger[key] = value
                    return value

                required = len(rows) - len(known)
                admissible = (sum(challenger) == sum(old)
                              and sum(challenger[i] for i in known) + required == sum(old)
                              and any(challenger[i] and not old[i] for i in known)
                              and (not old[1] or challenger[1])
                              and required <= extra)
                result = certified_tie('old', ('new',), rows, ledger, observe,
                                       extra=extra, metric_limit=len(initial) + extra)
                self.assertEqual(result, 'new' if admissible else None)
                self.assertLessEqual(len(ledger) - len(initial), extra)

    def test_extension_respects_an_exhausted_search_ceiling(self):
        rows = tuple(Row(str(i), 'validation') for i in range(3))
        ledger = {('old', '0'): Observation(False, {}), ('old', '1'): Observation(True, {}),
                  ('old', '2'): Observation(True, {}), ('new', '0'): Observation(True, {}),
                  ('new', '1'): Observation(False, {})}

        def observe(*args):
            self.fail('The existing search ceiling is exhausted')

        result = certified_tie('old', ('new',), rows, ledger, observe, extra=2, metric_limit=5)
        self.assertIsNone(result)
