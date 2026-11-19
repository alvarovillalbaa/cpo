from copy import deepcopy
from importlib.metadata import PackageNotFoundError, version
import json
import unittest

from benchmarks import grounded, grounded_fixture
from benchmarks.typed_policy import cohorts


try:
    GEPA_VERSION = version('gepa')
except PackageNotFoundError:
    GEPA_VERSION = None


class GroundedTests(unittest.TestCase):
    def test_same_prompt_receives_one_sample_per_repeat(self):
        case = cohorts()['outage']['holdout'][0]
        calls = []

        def dispatch(arm, role, instruction, inputs, *, repeat):
            calls.append((arm, role, instruction, inputs, repeat))
            return json.dumps(case['expected']) if repeat == 1 else '{}'

        selected = dict.fromkeys(('initial', *grounded.ARMS), 'same prompt')
        outcomes = grounded.qualify_task('outage', [case], selected, dispatch)
        self.assertEqual(calls, [
            ('paired', 'qualification', 'same prompt', case['input'], 0),
            ('paired', 'qualification', 'same prompt', case['input'], 1),
        ])
        self.assertEqual(outcomes[(case['id'], 0)], (case['critical'], dict.fromkeys(selected, False)))
        self.assertEqual(outcomes[(case['id'], 1)], (case['critical'], dict.fromkeys(selected, True)))

    @unittest.skipUnless(GEPA_VERSION == '0.1.4', 'requires pinned GEPA benchmark dependency')
    def test_paired_fixture_and_replay_keep_the_splits_separate(self):
        groups = cohorts(grounded.SEED)

        def verify_request(request):
            rows = groups[request['task']]
            if request['role'] == 'reflection':
                self.assertEqual(request['input']['labeledTraining'], [
                    {key: row[key] for key in ('id', 'input', 'expected')} for row in rows['train']
                ])
                serialized = json.dumps(request)
                for split in ('validation', 'holdout', 'confirmation'):
                    for case in rows[split]:
                        self.assertNotIn(case['id'], serialized)
                        self.assertNotIn(case['input'], serialized)
            else:
                splits = ('train', 'validation') if request['role'] == 'evaluation' else ('holdout',)
                self.assertIn(request['input'], {row['input'] for split in splits for row in rows[split]})
            return grounded_fixture.respond(request)

        report = grounded.run(verify_request, delivery='fixture')
        self.assertEqual(report['delivery'], 'fixture')
        self.assertEqual(set(report['outcome']['passesByTask']), {'initial', *grounded.ARMS})
        self.assertEqual(report['physicalSearchCalls'], 414)
        self.assertEqual(len(report['journal']) - report['physicalSearchCalls'], 216)
        self.assertEqual(grounded.replay(report), report)

        altered = deepcopy(report)
        altered['journal'][0]['request']['instruction'] += ' changed'
        with self.assertRaisesRegex(ValueError, 'request differs from replay'):
            grounded.replay(altered)


if __name__ == '__main__':
    unittest.main()
