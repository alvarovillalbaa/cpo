from unittest import TestCase

from benchmarks.alternative_controls import encode
from benchmarks.grounded import load_json
from benchmarks.opening_provisional_repair import cycle
from cpo import Observation, ProposalPair, Row


class ProvisionalRepairTests(TestCase):
    def setUp(self):
        self.train = [Row(f't{i}', 'task') for i in range(4)]
        self.validation = [Row(str(case), 'task', critical=case == 0) for case in range(5)]
        self.holdout = [Row('q0', 'task'), Row('q1', 'task')]
        self.outcomes = {'old': '10000', 'opening': '11000', 'sibling': '00000',
                         'tied': '11000', 'second': '11111'}
        self.parents, self.proof = [], []

    def evaluate(self, program, row):
        name = load_json(program)['instruction']
        passed = row.id.isdigit() and self.outcomes[name][int(row.id)] == '1'
        return Observation(passed, {}, int(passed))

    def propose(self, parent, feedback, history, width):
        name = load_json(parent)['instruction']
        self.parents.append(name)
        return ProposalPair(encode('tied' if name == 'opening' else 'second'), encode('sibling'))

    def qualify(self, program, row, repeat):
        name = load_json(program)['instruction']
        self.proof.append(name)
        return name != 'old'

    def run_cycle(self):
        return cycle(encode('old'), self.train, self.validation, self.holdout, self.evaluate, self.propose,
                     opening_pair=ProposalPair(encode('opening'), encode('sibling')), metric_limit=24,
                     qualify=self.qualify, seed=7, field_credit=False, repeats=2, rounds=6, train_per_round=2)

    def test_exact_tie_can_supply_context_but_only_the_strict_gain_qualifies(self):
        result = self.run_cycle()
        self.assertEqual(self.parents, ['opening', 'tied'])
        self.assertEqual(result.prompt, encode('second'))
        self.assertEqual(result.search.evaluations, 24)
        self.assertEqual(result.search.events[-1]['parentKind'], 'provisional')
        self.assertEqual(set(self.proof), {'old', 'second'})

    def test_same_total_with_different_passing_rows_is_ineligible(self):
        self.outcomes['tied'] = '10100'
        result = self.run_cycle()
        self.assertEqual(self.parents, ['opening'])
        self.assertEqual(result.prompt, encode('opening'))
        self.assertEqual(result.search.events[-1]['status'], 'first-repair-not-eligible')
        self.assertEqual(set(self.proof), {'old', 'opening'})

    def test_failed_followup_qualifies_the_last_strict_improvement(self):
        self.outcomes['second'] = '01111'
        result = self.run_cycle()
        self.assertEqual(self.parents, ['opening', 'tied'])
        self.assertEqual(result.search.events[-1]['status'], 'rejected')
        self.assertEqual(result.prompt, encode('opening'))
        self.assertEqual(set(self.proof), {'old', 'opening'})
