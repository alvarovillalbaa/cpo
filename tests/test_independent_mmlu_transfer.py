from copy import deepcopy
import unittest

from benchmarks.independent_mmlu_transfer import decode_panel


class IndependentMmluTransferTests(unittest.TestCase):
    viewer = {'features': [{'feature_idx': 1, 'name': 'example_1'}, {'feature_idx': 0, 'name': 'example_0'}],
              'rows': [{'row_idx': 0, 'row': {'example_1': 0, 'example_0': 1}, 'truncated_cells': []}],
              'num_rows_total': 1}

    def test_case_order_comes_from_the_source_schema(self):
        rows, digest = decode_panel(self.viewer, 1)
        self.assertEqual(rows, ['10'])
        self.assertEqual(len(digest), 64)

    def test_rejects_partial_rows_and_nonbinary_outcomes(self):
        for key, value in [('truncated_cells', ['example_1']), ('row', {'example_1': 2, 'example_0': 1}),
                           ('row_idx', 1), ('row', {'example_1': True, 'example_0': 1})]:
            with self.subTest(key=key, value=value):
                payload = deepcopy(self.viewer)
                payload['rows'][0][key] = value
                with self.assertRaises(ValueError):
                    decode_panel(payload, 1)
