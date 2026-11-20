"""T2 checks that the required-probe rule does not eliminate viable challengers."""

import unittest

from benchmarks import recorded_required_probe as study


class RequiredProbeTests(unittest.TestCase):
    def test_only_a_missed_singleton_is_a_required_probe(self):
        baseline = {'a': False, 'b': False, 'c': True, 'd': False}
        self.assertIsNone(study.required_miss(baseline, {'a': 'same', 'b': 'same', 'c': 'known'}))
        self.assertEqual(study.required_miss(baseline, {'a': 'same', 'b': 'same', 'd': 'rare'}), 'd')

    def test_required_first_funds_a_later_candidate_and_reuses_the_probe(self):
        rows = ('protected', 'required', 'ordinary')
        passes = {'initial': {'protected'}, 'rejected': {'protected', 'ordinary'}, 'winner': set(rows)}
        calls = []

        def evaluate(prompt, case):
            self.assertNotIn((prompt, case), calls)
            calls.append((prompt, case))
            return case in passes[prompt], 0

        result = study.select('initial', ('rejected', 'winner'), rows, {'protected': 'old', 'required': 'new'},
                              evaluate, lambda: len(calls), cap=7, width=4, policy='required-first')
        self.assertEqual(result, ('winner', 2))
        self.assertEqual(calls[3], ('rejected', 'required'))
        self.assertEqual(len(calls), 7)

    def test_empty_strata_reproduce_the_ordered_validation_race(self):
        rows = ('first', 'second', 'third')
        successes = {'initial': {'first'}, 'lost': {'second'}, 'better': {'first', 'third'}}

        def run(select):
            calls = []

            def evaluate(prompt, case):
                calls.append((prompt, case))
                return case in successes[prompt], 0

            result = select('initial', ('lost', 'better'), rows, {}, evaluate, lambda: len(calls))
            return result, calls

        expected = run(lambda *args: study.source.race(*args, cap=9, method=study.source.PRIMARY))
        for policy in study.METHODS:
            self.assertEqual(run(lambda *args: study.select(*args, cap=9, width=4, policy=policy)), expected)
