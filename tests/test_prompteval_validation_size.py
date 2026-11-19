import unittest

from benchmarks.prompteval_validation_size import compare, narrow_schedule


class ValidationSizeTests(unittest.TestCase):
    def test_only_the_validation_cohort_changes(self):
        layouts = [{'validation': [3, 8, 5], 'train': [2], 'qualify': [1, 4],
                    'alternatives': ['earlier', 'later'], 'seed': 42}]
        incumbent, narrowed = narrow_schedule('start', layouts, 2)
        self.assertEqual(incumbent, 'start')
        self.assertEqual(narrowed, [{**layouts[0], 'validation': [3, 8]}])
        self.assertEqual(layouts[0]['validation'], [3, 8, 5])

    def test_a_validation_prefix_must_exist_for_every_cycle(self):
        with self.assertRaisesRegex(ValueError, 'every scheduled panel'):
            narrow_schedule('start', [{'validation': [1, 2]}, {'validation': [3]}], 2)

    def test_pre_existing_gate_applies_to_cost_and_accuracy(self):
        incumbent = {'holdoutPasses': 8, 'searchLookups': 80, 'qualificationLookups': 20}
        for held, search, expected in ((8, 70, True), (8, 71, False), (9, 80, True), (7, 50, False)):
            with self.subTest(held=held, search=search):
                challenger = {**incumbent, 'holdoutPasses': held, 'searchLookups': search}
                self.assertEqual(compare(challenger, incumbent)['qualified'], expected)
