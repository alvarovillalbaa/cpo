"""T2 checks for the public coverage-aware pool selector."""

import unittest

from cpo import Observation, Row
from cpo.covered_pool import select_covered_pool
from cpo.pool import PoolResult


class CoveredPoolTests(unittest.TestCase):
    def test_early_veto_funds_a_later_fully_scored_candidate(self):
        rows = tuple(Row(key, 'test', key != 'ordinary') for key in ('ordinary', 'risk-a', 'risk-b', 'protected'))
        strata = {'risk-a': 'evidence', 'risk-b': 'evidence', 'protected': 'legacy'}
        passes = {'initial': {'protected'}, 'uncovered': {'ordinary', 'protected'}, 'winner': {row.id for row in rows}}
        reads = []

        def observe(prompt, row):
            reads.append((prompt, row.id))
            return Observation(row.id in passes[prompt], {})

        result = select_covered_pool(('initial', 'uncovered', 'winner'), rows, observe,
                                     metric_limit=11, critical_strata=strata)
        self.assertEqual(result, PoolResult('winner', 4, 11))
        self.assertNotIn(('uncovered', 'ordinary'), reads)
        self.assertEqual(len(reads), len(set(reads)))
        self.assertEqual({row for prompt, row in reads if prompt == 'winner'}, {row.id for row in rows})

    def test_no_unfunded_challenger_callback(self):
        rows = [Row('a', 'test', True), Row('b', 'test')]
        reads = []

        def observe(prompt, row):
            reads.append(prompt)
            return Observation(False, {})

        result = select_covered_pool(('initial', 'challenger'), rows, observe,
                                     metric_limit=3, critical_strata={'a': 'critical'})
        self.assertEqual(result, PoolResult('initial', 0, 2))
        self.assertEqual(reads, ['initial', 'initial'])

    def test_critical_coverage_mapping_is_validated_before_evaluation(self):
        rows = [Row('a', 'test', True), Row('b', 'test')]
        for mapping in ({}, {'a': 'risk', 'b': 'ordinary'}):
            with self.subTest(mapping=mapping), self.assertRaisesRegex(ValueError, 'each critical'):
                select_covered_pool(('initial', 'challenger'), rows, lambda *_: self.fail('Unexpected evaluation'),
                                    metric_limit=4, critical_strata=mapping)

    def test_equal_complete_scores_keep_the_earlier_candidate(self):
        rows = (Row('a', 'test'), Row('b', 'test'))
        result = select_covered_pool(('initial', 'first', 'second'), rows,
                                     lambda prompt, row: Observation(prompt != 'initial' and row.id == 'a', {}),
                                     metric_limit=6, critical_strata={})
        self.assertEqual(result, PoolResult('first', 1, 6))
