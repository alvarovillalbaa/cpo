from unittest import TestCase

from benchmarks import priced_gate_reachability as audit


class PricedGateReachabilityTests(TestCase):
    def test_repeated_validation_cost_and_earlier_offer(self):
        matrix = ['000000', '001010', '100001']
        layouts = [
            {'validation': [0, 1], 'qualify': [2, 3], 'alternatives': ['1']},
            {'validation': [0, 1], 'qualify': [4, 5], 'alternatives': ['2']},
        ]
        at_three = audit.paths(matrix, '0', layouts, 3)
        self.assertEqual(at_three[audit.ARCHIVE_MINIMUM], {'0': 0, '1': 3})
        self.assertEqual(at_three[audit.FRESH_MINIMUM], {'0': 0})
        self.assertEqual(at_three[audit.UNCAPPED], {'0': 0, '1': 3, '2': 4})
        self.assertEqual(audit.paths(matrix, '0', layouts, 4)[audit.FRESH_MINIMUM], {'0': 0, '2': 4})
        self.assertEqual(audit.paths(matrix, '0', layouts, 7)[audit.FRESH_DIRECT], {'0': 0})
        self.assertEqual(audit.paths(matrix, '0', layouts, 8)[audit.FRESH_DIRECT], {'0': 0, '2': 8})

    def test_positive_total_cannot_leave_start_with_a_half_regression(self):
        layouts = [{'validation': [0, 1], 'qualify': [2, 3, 4, 5], 'alternatives': ['1']}]
        results = audit.paths(['000010', '101100'], '0', layouts, 99)
        for mode in audit.MODELS:
            self.assertEqual(results[mode], {'0': 0})
        self.assertEqual(set(results[audit.ANY_OFFERED]), {'0', '1'})

    def test_cannot_chain_two_moves_in_one_cycle(self):
        # Prompt 2 can replace 1 with a strict gain. It cannot replace 0
        # because it loses the second qualification half relative to the start.
        matrix = ['00000010', '10100010', '11111000']
        layout = {'validation': [0, 1], 'qualify': [2, 3, 4, 5, 6, 7], 'alternatives': ['1', '2']}
        result = audit.paths(matrix, '0', [layout], 99)
        self.assertEqual(set(result[audit.UNCAPPED]), {'0', '1'})
