import unittest
from itertools import chain
from random import Random

from benchmarks.typed_policy import QUEUES, SPLITS, TASKS, cohorts, outage, warehouse


class TypedPolicyTests(unittest.TestCase):
    def test_cohorts_reproduce_and_have_disjoint_inputs(self):
        first = cohorts()
        self.assertEqual(first, cohorts())
        self.assertNotEqual(first, cohorts(41492))
        self.assertEqual(tuple(first), TASKS)
        for groups in first.values():
            self.assertEqual({split: len(rows) for split, rows in groups.items()}, SPLITS)
            rows = tuple(chain.from_iterable(groups.values()))
            for key in ('id', 'input'):
                self.assertEqual(len({row[key] for row in rows}), len(rows))
            self.assertTrue(all(any(row['critical'] for row in split) for split in groups.values()))

    def test_ticket_training_has_all_canonical_values_and_fallback(self):
        train = cohorts()['ticket']['train']
        self.assertEqual({row['expected']['queue'] for row in train}, {*QUEUES.values(), 'GENERAL'})

    def test_warehouse_training_has_all_actions_and_zero_stock_examples(self):
        for rows in cohorts()['warehouse'].values():
            self.assertEqual({row['expected']['action'] for row in rows}, {'HOLD', 'RELEASE', 'REVIEW'})
            self.assertEqual({row['expected']['owner'] for row in rows}, {'CREW-N', 'CREW-S'})
        for stock in ('depleted', 'zero'):
            _, expected, _ = warehouse(1, Random(2), (stock, 'PASS', 'RUSH', 'NORTH'))
            self.assertEqual(expected, {'available': 0, 'action': 'HOLD', 'owner': 'CREW-N', 'windowHours': 4})

    def test_outage_evidence_covers_inclusive_thresholds_and_precedence(self):
        for duration, credit, review, reason in ((29, 0, False, 'NORMAL'), (30, 6, False, 'NORMAL'),
                                                 (119, 23, False, 'NORMAL'), (120, 24, True, 'LONG')):
            _, expected, _ = outage(10, Random(2), (duration, 'STANDARD', False, 'POSTED'))
            self.assertEqual(expected, {'credit': credit, 'review': review, 'reason': reason})
        facts, expected, _ = outage(10, Random(2), (121, 'PLUS', True, 'MISSING'))
        fee = int(facts.split('USD=')[1].split(';')[0])
        self.assertEqual(expected, {'credit': fee // 10, 'review': True, 'reason': 'NEEDS_DOC'})


if __name__ == '__main__':
    unittest.main()
