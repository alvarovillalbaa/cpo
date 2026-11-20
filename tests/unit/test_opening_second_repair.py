from unittest import TestCase

from benchmarks.alternative_controls import encode
from benchmarks.grounded import load_json
from benchmarks.opening_second_repair import second_repair_cycle
from cpo import Observation, ProposalPair, Row


class SecondOpeningRepairTests(TestCase):
    def setUp(self):
        self.train = [Row(f't{i}', 'task') for i in range(4)]
        self.validation = [Row(str(case), 'task', critical=case == 0) for case in range(5)]
        self.holdout = [Row('q0', 'task'), Row('q1', 'task')]
        self.known = {'old': '10000', 'opening': '11000', 'sibling': '00000',
                      'first': '11100', 'second': '11111'}
        self.programs = {name: encode(name, () if name == 'old' else (0,)) for name in self.known}
        self.feedback, self.proof, self.evaluations = [], [], []

    def evaluate(self, program, row):
        self.evaluations.append((program, row.id))
        name = load_json(program)['instruction']
        return Observation(row.id.isdigit() and self.known[name][int(row.id)] == '1', {})

    def propose(self, parent, feedback, _history, width):
        self.assertEqual(width, 1)
        name = load_json(parent)['instruction']
        self.feedback.append({row.id for row, _ in feedback})
        next_prompt = self.programs['first' if name == 'opening' else 'second']
        return ProposalPair(next_prompt, self.programs['sibling'])

    def qualify(self, prompt, row, repeat):
        self.proof.append((prompt, row.id, repeat))
        return prompt != self.programs['old']

    def run_cycle(self, cap=24):
        return second_repair_cycle(
            self.programs['old'], self.train, self.validation, self.holdout, self.evaluate, self.propose,
            opening_pair=ProposalPair(self.programs['opening'], self.programs['sibling']),
            metric_limit=cap, qualify=self.qualify, seed=9, field_credit=False, repeats=2, rounds=6, train_per_round=2)

    def test_second_repair_uses_new_training_rows_and_qualifies_once(self):
        result = self.run_cycle()
        self.assertEqual(result.prompt, self.programs['second'])
        self.assertEqual(result.search.reflections, 2)
        self.assertEqual(result.search.evaluations, 24)
        self.assertEqual(len(self.evaluations), len(set(self.evaluations)))
        self.assertEqual([len(rows) for rows in self.feedback], [2, 2])
        self.assertFalse(self.feedback[0].intersection(self.feedback[1]))
        self.assertEqual({prompt for prompt, _, _ in self.proof},
                         {self.programs['old'], self.programs['second']})

    def test_unfunded_second_repair_leaves_first_nominee(self):
        result = self.run_cycle(cap=22)
        self.assertEqual(result.prompt, self.programs['first'])
        self.assertEqual(result.search.events[-1]['status'], 'unfunded')
        self.assertEqual(result.search.reflections, 1)
        self.assertEqual(result.search.evaluations, 17)

    def test_rejected_first_repair_does_not_open_another_round(self):
        self.known['first'] = self.known['opening']
        result = self.run_cycle()
        self.assertEqual(result.prompt, self.programs['opening'])
        self.assertEqual(result.search.events[-1]['status'], 'first-repair-not-accepted')
        self.assertEqual(result.search.reflections, 1)

    def test_second_repair_cannot_trade_away_a_critical_pass(self):
        self.known['second'] = '01111'
        result = self.run_cycle()
        self.assertEqual(result.prompt, self.programs['first'])
        self.assertEqual(result.search.events[-1]['status'], 'rejected')
        self.assertNotIn(self.programs['second'], {prompt for prompt, _, _ in self.proof})
