from unittest import TestCase

from benchmarks.alternative_controls import encode
from benchmarks.grounded import load_json
from benchmarks.opening_repair_probe_routing import repaired_cycle, select_probes
from cpo import Observation, ProposalPair, Row


class ProbeRoutingTests(TestCase):
    def test_failed_feature_beats_a_feature_shared_by_all_rows(self):
        train = [Row('other', 'task'), Row('target', 'task')]
        features = {'other': (('zone', 'a'), ('shared', 'x')),
                    'target': (('zone', 'b'),),
                    'v0': (('zone', 'a'), ('shared', 'x')),
                    'v1': (('zone', 'b'), ('shared', 'x'))}
        result = select_probes(train, [('v0', True), ('v1', False)], features, 1)
        self.assertEqual([row.id for row in result], ['target'])

    def test_ties_keep_the_established_training_order(self):
        train = [Row('second', 'task'), Row('first', 'task')]
        features = {key: (('zone', 'a'),) for key in ('v0', 'v1', 'first', 'second')}
        self.assertEqual(select_probes(train, [('v0', True), ('v1', False)], features, 2), train)

    def test_only_routed_training_replies_reach_the_proposer(self):
        train = [Row(f't{i}', 'task') for i in range(3)]
        validation = [Row(str(i), 'task') for i in range(4)]
        holdout = [Row('q0', 'task'), Row('q1', 'task')]
        features = {key: (('regime', 'typical'),) for key in ('t0', '0', '1')}
        features.update({key: (('regime', 'failing'),) for key in ('t1', 't2', '2', '3')})
        values = {'old': '1000', 'opening': '1100', 'other': '0000', 'repaired': '1111'}
        reflected, proved = [], []

        def evaluate(program, row):
            prompt = load_json(program)['instruction']
            passed = values[prompt][int(row.id)] == '1' if row.id.isdigit() else row.id == 't0'
            return Observation(passed, {'id': row.id})

        def propose(parent, feedback, history, width):
            reflected.extend(reply.feedback['id'] for _, reply in feedback)
            self.assertEqual((history, width), ([], 1))
            return ProposalPair(encode('repaired'), encode('other'))

        def qualify(program, row, repeat):
            proved.append(load_json(program)['instruction'])
            return program == encode('repaired')

        result = repaired_cycle(features)(
            encode('old'), train, validation, holdout, evaluate, propose,
            opening_pair=ProposalPair(encode('opening'), encode('other')), metric_limit=14, qualify=qualify,
            seed=11, field_credit=False, repeats=2, rounds=6, train_per_round=2)
        self.assertEqual(result.prompt, encode('repaired'))
        self.assertEqual(set(reflected), {'t1', 't2'})
        self.assertEqual(set(proved), {'old', 'repaired'})
        self.assertEqual(result.search.evaluations, 14)
