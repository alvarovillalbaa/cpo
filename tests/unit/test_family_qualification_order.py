from itertools import product
from unittest import TestCase

from cpo import Row
from cpo.expected_qualification import certify_expected_qualification
from cpo.paired_qualification import certify_paired_qualification


class FamilyQualificationOrderTests(TestCase):
    def test_binary_family_decisions_and_aggregate_modeled_cost(self):
        rows = [Row(str(i), str(i // 2)) for i in range(4)]
        lookups = {'baseline': 0, 'ordered': 0}
        for outcomes in product((False, True), repeat=8):
            values = dict(zip(product(('old', 'new'), range(4)), outcomes, strict=True))
            expected = [int(values['new', i]) - int(values['old', i]) for i in range(4)]

            def read(prompt, row, repeat):
                self.assertEqual(repeat, 0)
                return values[prompt, int(row.id)]

            baseline = certify_paired_qualification('old', 'new', rows, read)
            ordered = certify_expected_qualification('old', 'new', rows, read)
            promoted = sum(expected) > 0 and sum(expected[:2]) >= 0 and sum(expected[2:]) >= 0
            self.assertEqual(ordered.prompt, 'new' if promoted else 'old')
            self.assertEqual(ordered.status, baseline.status)
            keys = {(item.prompt, item.row_id) for item in ordered.observations}
            self.assertEqual(len(keys), len(ordered.observations))
            lookups['baseline'] += len(baseline.observations)
            lookups['ordered'] += len(ordered.observations)
        self.assertLess(lookups['ordered'], lookups['baseline'])

    def test_preserve_unresolved_status_at_budget_limit(self):
        rows = [Row('a', 'alpha'), Row('b', 'beta')]
        choice = certify_expected_qualification('old', 'new', rows, lambda *args: True, evaluation_limit=1)
        self.assertEqual(choice.status, 'undecided')
        self.assertEqual(choice.prompt, 'old')
        self.assertEqual(len(choice.observations), 1)

    def test_keep_critical_and_repeat_contract(self):
        rows = [Row('a', 'alpha', True), Row('b', 'beta')]

        def read(prompt, row, repeat):
            return (prompt == 'old') == (row.id == 'a')

        original = certify_paired_qualification('old', 'new', rows, read, repeats=2)
        ordered = certify_expected_qualification('old', 'new', rows, read, repeats=2)
        self.assertEqual(original, ordered)
        self.assertEqual(ordered.prompt, 'old')
