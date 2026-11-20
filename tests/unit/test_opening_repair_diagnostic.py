from unittest import TestCase

from benchmarks.alternative_controls import encode
from benchmarks.grounded import load_json
from benchmarks.opening_repair_diagnostic import diagnostic_cycle
from benchmarks.opening_screen_repair import staged_cycle
from cpo import Observation, ProposalPair, Row


class RepairDiagnosticTests(TestCase):
    def setUp(self):
        self.training = [Row('t0', 'task'), Row('t1', 'task')]
        self.validation = [Row(str(case), 'task', critical=case == 0) for case in range(4)]
        self.qualification = [Row('q0', 'task'), Row('q1', 'task')]
        self.old = encode('old')
        self.first = encode('first', [0, 1])
        self.repaired = encode('repaired', [0, 1])
        self.values = {'old': '1000', 'first': '1100', 'repair': '0000', 'repaired': '1111'}
        self.search, self.reflections, self.proof = [], [], []

    def observe(self, program, row):
        self.search.append((program, row.id))
        spec = load_json(program)
        passed = (self.values[spec['instruction']][int(row.id)] == '1' if row.id.isdigit()
                  else bool(spec['demos']))
        return Observation(passed, {'id': row.id})

    def propose(self, parent, samples, history, width):
        self.reflections.append((parent, samples, history, width))
        return ProposalPair(self.repaired, encode('repair', [0, 1]))

    def qualify(self, program, row, repeat):
        self.proof.append((program, row.id, repeat))
        return program != self.old

    def run_cycle(self, operation):
        return operation(self.old, self.training, self.validation, self.qualification, self.observe, self.propose,
                         metric_limit=14, rounds=6, train_per_round=2, opening_pair=ProposalPair(
                             self.first, encode('repair', [0, 1])),
                         qualify=self.qualify, seed=19, field_credit=False, repeats=1)

    def test_only_training_probes_remove_demonstrations(self):
        normal = self.run_cycle(staged_cycle(2))
        self.assertEqual(normal.prompt, self.first)
        self.assertEqual(self.reflections, [])
        self.search.clear()
        self.proof.clear()

        diagnostic = self.run_cycle(diagnostic_cycle())
        self.assertEqual(diagnostic.prompt, self.repaired)
        self.assertEqual(diagnostic.search.evaluations, 14)
        self.assertEqual({p for p, row in self.search if row.startswith('t')}, {encode('first')})
        self.assertEqual({p for p, row in self.search if row.isdigit()},
                         {self.old, self.first, self.repaired})
        parent, samples, _, _ = self.reflections[0]
        self.assertEqual(parent, self.first)
        self.assertEqual(len(samples), 2)
        self.assertTrue(all(not receipt.passed for _, receipt in samples))
        self.assertEqual({p for p, _, _ in self.proof}, {self.old, self.repaired})

    def test_perfect_opening_dispatches_no_diagnostic_probes(self):
        self.values['first'] = '1111'
        result = self.run_cycle(diagnostic_cycle())
        self.assertEqual(result.prompt, self.first)
        self.assertEqual(result.search.events[-1]['probes'], [])
        self.assertEqual(self.reflections, [])
