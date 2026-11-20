import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from benchmarks import grounded_staged as study, grounded_staged_fixture as fixture
from cpo._contract import digest


class GroundedStagedTests(TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory(prefix='cpo-grounded-staged-test-')))
        self.groups, self.plan, _ = study.prepare()
        self.seal = digest(self.plan)

    def test_development_and_confirmation_replay_match_their_full_journals(self):
        development = self.root / 'development'
        indexed = {task: {row['input']: split for split, rows in groups.items() for row in rows}
                   for task, groups in self.groups.items()}
        observed = []

        def respond(request):
            observed.append(request)
            task, role = request['task'], request['role']
            if role == 'reflection':
                training = {row['id'] for row in self.groups[task]['train']}
                self.assertEqual({row['id'] for row in request['input']['labeledTraining']}, training)
                self.assertTrue(all(row['id'] in training for row in request['input']['recentFeedback']))
            else:
                split = indexed[task][request['input']]
                allowed = {'admission': ('admission',), 'evaluation': ('train', 'validation'),
                           'qualification': ('holdout',)}
                self.assertIn(split, allowed[role])
                self.assertNotIn('expected', request)
            return fixture.respond(request)

        result = study.run(self.seal, development, respond, delivery='fixture')
        self.assertTrue(result['outcome']['qualified'])
        self.assertEqual(sum(result['physicalCallsByRole'].values()), len(observed))
        self.assertEqual(study.replay(development, self.root / 'development-replay'), result)
        _, plan, _ = study.prepare(development)
        self.assertEqual(plan['developmentArchiveSha256'].keys(), set(study.ARCHIVE_FILES))
        self.assertEqual(plan['developmentDelivery'], 'fixture')
        self.assertEqual(plan['promptsSha256'], digest(result['selected']))

        def confirm(request):
            self.assertEqual(request['role'], 'qualification')
            self.assertEqual(indexed[request['task']][request['input']], 'confirmation')
            return fixture.respond(request)

        confirmation = self.root / 'confirmation'
        independent = study.run(digest(plan), confirmation, confirm, delivery='fixture', development=development)
        self.assertTrue(independent['outcome']['qualified'])
        self.assertEqual(independent['selected'], result['selected'])
        self.assertEqual(study.replay(confirmation, self.root / 'confirmation-replay', development=development), independent)
        refused = self.root / 'invalid-model-confirmation'
        with self.assertRaisesRegex(ValueError, 'delivery'):
            study.run(digest(plan), refused, lambda *_: self.fail('Responder called'),
                      delivery='model', development=development)
        self.assertFalse(refused.exists())

    def test_a_failed_reply_leaves_one_unmatched_request_and_no_result(self):
        directory = self.root / 'broken'
        calls = 0

        def respond(request):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('lost reply')
            return fixture.respond(request)

        with self.assertRaisesRegex(OSError, 'lost reply'):
            study.run(self.seal, directory, respond, delivery='fixture')
        self.assertEqual(calls, 2)
        events = [json.loads(line) for line in (directory / 'wire.jsonl').read_text().splitlines()]
        self.assertEqual([event['sequence'] for event in events], [1, 1, 2])
        self.assertEqual(events[-1]['request']['role'], 'evaluation')
        self.assertFalse((directory / 'result.json').exists())

    def test_failed_development_cannot_bind_independent_confirmation(self):
        development = self.root / 'failed'

        def respond(request):
            return '{}' if request['role'] == 'qualification' else fixture.respond(request)

        result = study.run(self.seal, development, respond, delivery='fixture')
        self.assertFalse(result['outcome']['qualified'])
        with self.assertRaisesRegex(ValueError, 'qualifying development'):
            study.prepare(development)

    def test_stale_seal_fails_before_creating_an_archive(self):
        target = self.root / 'stale'
        with self.assertRaisesRegex(ValueError, 'current seal'):
            study.run('0' * 64, target, lambda *_: self.fail('Responder called'), delivery='fixture')
        self.assertFalse(target.exists())

    def test_certified_protocol_replays_and_cannot_bind_full_validation(self):
        reference, certified, confirmation = (self.root / name for name in ('full', 'certified', 'confirmation'))
        full = study.run(self.seal, reference, fixture.respond, delivery='fixture')
        _, plan, _ = study.prepare(certify_final_draft=True)
        self.assertTrue(plan['certifyFinalDraft'])
        self.assertIn('cpo/anchored_validation.py', plan['sourceSha256'])
        self.assertEqual(plan['logicalLimitsByRole'], self.plan['logicalLimitsByRole'])
        with self.assertRaisesRegex(ValueError, 'current seal'):
            study.run(self.seal, certified, lambda *_: self.fail('Responder called'),
                      delivery='fixture', certify_final_draft=True)
        result = study.run(digest(plan), certified, fixture.respond, delivery='fixture', certify_final_draft=True)
        for key in ('selected', 'admissionDecisions', 'holdout', 'outcome'):
            self.assertEqual(result[key], full[key])
        self.assertLessEqual(result['logicalCallsByRole']['evaluation'], full['logicalCallsByRole']['evaluation'])
        self.assertEqual(study.replay(certified, self.root / 'verified'), result)
        with self.assertRaisesRegex(ValueError, 'current seal'):
            study.prepare(certified)
        with self.assertRaisesRegex(ValueError, 'current seal'):
            study.prepare(reference, certify_final_draft=True)
        _, bound, _ = study.prepare(certified, certify_final_draft=True)
        panel = study.run(digest(bound), confirmation, fixture.respond, delivery='fixture', development=certified,
                          certify_final_draft=True)
        self.assertTrue(panel['outcome']['qualified'])
        self.assertEqual(study.replay(confirmation, self.root / 'verified-panel', development=certified), panel)

    def test_combined_protocol_binds_both_certificates_and_rejects_single_certificate(self):
        from benchmarks.grounded_staged_combined_fixture import mixed_fixture

        single, combined = self.root / 'single', self.root / 'combined'
        _, prior, _ = study.prepare(certify_final_draft=True)
        baseline = study.run(digest(prior), single, mixed_fixture, delivery='fixture', certify_final_draft=True)
        flags = {'certify_final_draft': True, 'certify_opening': True}
        _, frozen, _ = study.prepare(**flags)
        self.assertEqual(frozen['protocol'], 'portable-grounded-staged-combined-v1')
        self.assertTrue(frozen['certifyOpening'] and frozen['certifyFinalDraft'])
        self.assertIn('cpo/opening_certificate.py', frozen['sourceSha256'])
        self.assertEqual(prior['logicalLimitsByRole'], frozen['logicalLimitsByRole'])
        current = study.run(digest(frozen), combined, mixed_fixture, delivery='fixture', **flags)
        self.assertEqual(current['selected'], baseline['selected'])
        self.assertEqual(current['admissionDecisions'], baseline['admissionDecisions'])
        self.assertEqual(current['holdout'], baseline['holdout'])
        self.assertLess(current['searchCallsByArm']['cpo'], baseline['searchCallsByArm']['cpo'])
        self.assertEqual(study.replay(combined, self.root / 'replayed'), current)
        with self.assertRaisesRegex(ValueError, 'current seal'):
            study.prepare(combined, certify_final_draft=True)
        with self.assertRaisesRegex(ValueError, 'current seal'):
            study.prepare(single, **flags)
