from itertools import product
import unittest

from benchmarks.recorded_validation_stability import guarded_race, run_trial
from cpo import Observation, Row


class RecordedValidationStabilityTests(unittest.TestCase):
    def test_pruning_matches_exhaustive_ranking(self):
        rows = tuple(Row(str(i), 'validation', critical=i == 0) for i in range(4))
        roster = ('first', 'second')
        for bits in product((False, True), repeat=12):
            start = bits[:4]
            replies = {'start': start, 'first': bits[4:8], 'second': bits[8:]}
            for individual in (False, True):
                ledger = {}

                def observe(prompt, row):
                    key = prompt, row.id
                    if key in ledger:
                        self.fail('A validation lookup was repeated')
                    outcome = Observation(replies[prompt][int(row.id)], {})
                    ledger[key] = outcome
                    return outcome

                def eligible(candidate):
                    if start[0] and not candidate[0]:
                        return False
                    if individual:
                        return all(not base or new for base, new in zip(start, candidate, strict=True))
                    return sum(candidate[:2]) >= sum(start[:2]) and sum(candidate[2:]) >= sum(start[2:])

                options = ('start', *(prompt for prompt in roster if eligible(replies[prompt])))
                expected = max(options, key=lambda prompt: sum(replies[prompt]))
                actual = guarded_race('start', roster, rows, observe, ledger, cap=12, individual=individual)
                self.assertEqual(actual, expected)
                self.assertLessEqual(len(ledger), 12)

    def test_rank_eligible_before_independent_qualification(self):
        cohorts = ([0, 1], [2, 3, 4, 5], [6, 7], [8, 9])
        replies = {'start': '0011000000', 'first': '0010111110', 'second': '0011101011'}
        cells = {prompt: [(int(bit), 3, False) for bit in values] for prompt, values in replies.items()}
        roster = ('first', 'second')
        veto, veto_trace, _ = run_trial(cells, 'start', roster, cohorts, 0, 'split-veto', 12)
        raced, race_trace, _ = run_trial(cells, 'start', roster, cohorts, 0, 'split-race', 12)
        self.assertEqual(veto_trace[2:4], ('start', 'start'))
        self.assertEqual(race_trace[2:4], ('second', 'second'))
        self.assertEqual((veto['holdoutPasses'], raced['holdoutPasses']), (0, 2))
        self.assertEqual(veto['qualificationLookups'], 1)
        self.assertLessEqual(raced['qualificationLookups'], 4)
        self.assertLessEqual(raced['searchLookups'], 12)
        self.assertEqual(raced['historicalCostNanodollars'], 3 * raced['paidLookups'])

    def test_reserves_a_complete_challenge(self):
        rows = tuple(Row(str(i), 'validation') for i in range(4))
        ledger = {}

        def observe(prompt, row):
            self.assertEqual(prompt, 'start')
            ledger[prompt, row.id] = Observation(False, {})
            return ledger[prompt, row.id]

        result = guarded_race('start', ('challenger',), rows, observe, ledger, cap=7, individual=False)
        self.assertEqual(result, 'start')
        self.assertEqual(len(ledger), 4)
