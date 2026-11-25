"""Audit exact reply grading and reject malformed Unicode in paid drafts."""

import argparse
from collections import Counter
from contextlib import contextmanager, nullcontext
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from benchmarks import first_gain_native_feedback as native
from benchmarks import first_gain_regime_confirmation as confirmation
from cpo._contract import digest


study = native.previous
grounded = study.grounded
ROOT = native.ROOT
NATIVE_SHA = '3da4f61194d428ecae131ae1c6df768593de46ce1a448b72108eae31f9e9b2a2'
REGIME_SHA = 'fc04fc18069c29b0a6539025d050d5f2d7df095b9a86f30bd0522fa13dde3ec1'
_PROPOSALS = grounded.proposals
MALFORMED = '{"instruction":"\\ud800"}'


def proposals(text, parent, keys):
    try:
        return _PROPOSALS(text, parent, keys)
    except UnicodeEncodeError:
        # A JSON-escaped lone surrogate parses as a string but cannot be
        # enrolled as UTF-8. Reject the whole proposed draft or pair.
        return ()


@contextmanager
def guarded_drafts():
    with patch.object(grounded, 'proposals', proposals):
        yield


def value_audit(cases):
    counts = Counter()
    for case in cases:
        expected = case['expected']
        text = json.dumps(expected)
        if grounded.score(text, expected) != (True, len(expected)):
            raise ValueError('Every sealed exact answer must pass and get full field credit')
        counts['exactAnswers'] += 1
        for key, value in expected.items():
            if type(value) is int:
                variants = [float(value), str(value)]
                if value in (0, 1):
                    variants.append(bool(value))
            elif type(value) is bool:
                variants = [int(value)]
            else:
                variants = [None, 0]
            for mistake in variants:
                if grounded.score(json.dumps({**expected, key: mistake}), expected) != (False, 0):
                    raise ValueError('A scalar type mutation must fail exact and partial scoring')
                counts['wrongTypeRejections'] += 1
            escaped = '"\\u%04x%s"' % (ord(key[0]), key[1:])
            duplicate = f'{text[:-1]},{escaped}:{json.dumps(value)}}}'
            if grounded.score(duplicate, expected) != (False, 0):
                raise ValueError('An alternate spelling of a duplicate key must fail scoring')
            counts['duplicateKeyRejections'] += 1
    return counts


def prepare():
    tasks, _, parent, _ = native.prepare()
    lock = study.shared.prior.prior.locked
    original = lock('first-gain-native-feedback-v1.json', NATIVE_SHA)
    regime, panel, panel_tasks = confirmation.prepare()
    panel_result = lock('first-gain-regime-confirmation-v1.json', REGIME_SHA)
    if (digest(parent) != original['planSha256'] or digest(original['plan']) != original['planSha256']
            or tasks != panel_tasks or digest(regime) != panel_result['planSha256']
            or digest(panel) != digest(panel_result['rows'])):
        raise ValueError('The corrected comparison and independent panel must reproduce')
    source = Path(__file__)
    plan = {**parent, 'protocol': 'cpo-first-gain-independent-response-robustness-v1',
            'sampledFeedbackPlanSha256': digest(parent), 'sampledFeedbackReceiptSha256': NATIVE_SHA,
            'regimeManifestSha256': REGIME_SHA, 'panelSha256': digest(panel),
            'sourceSha256': {**parent['sourceSha256'], source.relative_to(ROOT).as_posix():
                             sha256(source.read_bytes()).hexdigest()},
            'draftFailureRule': 'Reject the paid proposal when its parsed instruction cannot be encoded as UTF-8.'}
    return tasks, panel, plan, original


def malformed_fixture(tasks, plan, output, *, protected):
    scripted = study.fixture(tasks)
    injected = []

    def respond(request):
        value = scripted(request)
        if request['role'] == 'reflection' and not injected:
            injected.append(request)
            return MALFORMED
        return value

    guard = guarded_drafts() if protected else nullcontext()
    with (study.configured(tasks, plan), guard, patch.object(study, 'cycle', partial(native.cycle, True, []))):
        result = study.parent.run(digest(plan), output, respond, delivery='fixture')
    audit = study.audit(tasks, result, output)
    events = [grounded.load_json(line) for line in (output / 'wire.jsonl').read_bytes().splitlines()]
    pairs = [(ask, reply) for ask, reply in zip(events[::2], events[1::2], strict=True)
             if reply['response'] == MALFORMED]
    if len(pairs) != 1 or injected != [pairs[0][0]['request']] or any(
            result['physicalCallsByRole'][role] > ceiling for role, ceiling in plan['physicalLimitsByRole'].items()):
        raise ValueError('The malformed draft must stay in the journal and fit the original request caps')
    first = result['decisions'][pairs[0][0]['request']['task']][pairs[0][0]['arm']][0]
    if first['drafts'] < 1 or first['drafts'] - len(first['roster']) != 1:
        raise ValueError('The malformed draft must consume an attempt without entering the roster')
    return {'physicalRequestsByRole': result['physicalCallsByRole'], 'holdoutRequests': audit['holdoutRequests'],
            'malformedDraftOwner': pairs[0][0]['arm'], 'malformedDraftSequence': pairs[0][0]['sequence'],
            'chargedAttempts': first['drafts'], 'enrolledDrafts': len(first['roster'])}


def verify(tasks, panel, plan, prior, work):
    cases = [row for splits in tasks.values() for rows in splits.values() for row in rows]
    cases.extend(row for rows in panel.values() for row in rows)
    typed = value_audit(cases)
    with guarded_drafts():
        clean, _ = native.run_fixture(tasks, plan, work / 'ordinary', use_sampled=True)
    clean_dir = work / 'ordinary'
    normalized = json.dumps({**clean, 'planSha256': prior['planSha256']}, indent=2, sort_keys=True) + '\n'
    original = prior['correctedArchiveSha256']
    if (sha256(normalized.encode()).hexdigest() != original['result.json'] or any(
            sha256((clean_dir / name).read_bytes()).hexdigest() != original[name]
            for name in ('wire.jsonl', study.AUDIT))):
        raise ValueError('Ordinary corrected responses must reproduce their exact journals and outcomes')

    previous_dir = work / 'original-malformed'
    try:
        malformed_fixture(tasks, prior['plan'], previous_dir, protected=False)
    except UnicodeEncodeError:
        if (previous_dir / 'result.json').exists():
            raise ValueError('The old failure must precede the final result')
    else:
        raise ValueError('The malformed draft must reproduce the original exception')
    measured = malformed_fixture(tasks, plan, work / 'rejected-draft', protected=True)
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'typedGrades': typed,
            'ordinaryCorrectedReplayMatched': True, 'originalFailure': 'UnicodeEncodeError',
            'malformedDraftRehearsal': measured}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--fixture', metavar='PLAN_SHA256')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    tasks, panel, plan, prior = prepare()
    seal = digest(plan)
    if not (args.fixture or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.fixture != seal or args.out is None or args.out.exists():
        cli.error('Use the current fixture seal and a fresh output path')
    with TemporaryDirectory(prefix='cpo-response-robustness-') as scratch:
        report = verify(tasks, panel, plan, prior, Path(scratch))
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
