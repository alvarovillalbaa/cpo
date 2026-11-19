from collections import Counter
import unittest

from benchmarks.prompteval_paid_witness import select_witness, use_history
from cpo import Observation, Row
from cpo.single_finalist import select_single_finalist


class PaidWitnessTests(unittest.TestCase):
    def test_rule_ignores_incumbent_evidence_and_retains_row_order_on_ties(self):
        first, second = rows = (Row('first', 'task'), Row('second', 'task'))
        history = {'first': {'incumbent': False, 'old-1': False}}
        self.assertEqual(select_witness(rows, 'incumbent', history, 'avoid-two-failures'), first)
        history['first']['old-2'] = False
        self.assertEqual(select_witness(rows, 'incumbent', history, 'avoid-two-failures'), second)
        self.assertEqual(select_witness(rows, 'incumbent', {}, 'smoothed-pass-rate'), first)

    def test_same_paid_rows_can_nominate_a_candidate_on_a_different_miss(self):
        rows = tuple(Row(case, 'task') for case in ('good', 'miss', 'other'))
        history = {'miss': {'old-1': False, 'old-2': False}}
        paid = []

        def evaluate(prompt, row):
            paid.append((prompt, row.id))
            return Observation(row.id in ({'good'} if prompt == 'current' else {'good', 'other'}), {})

        audit = Counter()
        result = use_history('current', ('new',), rows, evaluate, metric_limit=6, history=history,
                             policy='avoid-two-failures', audit=audit)
        self.assertEqual(result.prompt, 'new')
        self.assertEqual(audit['changedWitness'], 1)
        self.assertEqual(paid[3], ('new', 'other'))
        self.assertEqual(len(paid), len(set(paid)))
        self.assertEqual(result.evaluations, len(paid))
        self.assertIs(history['other']['new'], True)

    def test_empty_history_preserves_the_first_gain_calls_and_decision(self):
        rows = (Row('a', 'task'), Row('b', 'task'), Row('c', 'task'))
        calls = []

        def evaluate(prompt, row):
            calls.append((prompt, row.id))
            return Observation(prompt == 'new' or row.id == 'b', {})

        baseline = select_single_finalist('old', ('new',), rows, evaluate, metric_limit=6, screen='first-gain')
        expected = calls.copy()
        calls.clear()
        result = use_history('old', ('new',), rows, evaluate, metric_limit=6, history={},
                             policy='smoothed-pass-rate', audit=Counter())
        self.assertEqual(result, baseline)
        self.assertEqual(calls, expected)
