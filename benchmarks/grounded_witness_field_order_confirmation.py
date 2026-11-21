"""Run a sealed field-order confirmation from a qualifying ordered development archive."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import grounded, grounded_staged as staged, grounded_witness_ordered_futility as ordered
from benchmarks import witness_confirmation_field_order as evidence
from cpo._contract import digest


ROOT = ordered.original.ROOT
RECEIPT = 'docs/witness-confirmation-field-order-results-v1.json'
RECEIPT_SHA256 = 'f8abb7fa5db23327653edbaf7be2276f0b7fc6144ade7611bd181b4ef5283908'
PROFILES = ('qualifying', 'single-miss', 'shared-failure')
archive_bytes = ordered.archive_bytes


def prepare(development):
    raw = (ROOT / RECEIPT).read_bytes()
    if sha256(raw).hexdigest() != RECEIPT_SHA256:
        raise ValueError('Use the published field-order evidence')
    recorded = grounded.load_json(raw)
    _, _, tested = evidence.prepare()
    if digest(tested) != recorded['planSha256']:
        raise ValueError('The published field-order study did not reproduce')
    groups, parent, prior = ordered.prepare(development)
    shifted, probes = evidence.confirmation_panels(groups)
    panel_hash = digest({task: regions['confirmation'] for task, regions in shifted.items()})
    if panel_hash != tested['confirmationDatasetSha256'] or probes != tested['probeIdsByTask']:
        raise ValueError('The confirmation cases differ from the published field-order study')
    samples = ordered.study.order(ordered.original.scoring_schedule(shifted, prior['selected'], 'confirmation'),
                                  ordered.study.GATE)
    if len(samples) != parent['requestCeiling'] or len({digest(sample.request) for sample in samples}) != len(samples):
        raise ValueError('The field-order schedule must preserve the distinct request ceiling')
    sources = {Path(__file__).resolve().relative_to(ROOT).as_posix(): sha256(Path(__file__).read_bytes()).hexdigest()}
    plan = {**parent, 'protocol': 'portable-grounded-witness-field-order-confirmation-v1',
            'parentConfirmationPlanSha256': digest(parent), 'fieldOrderEvidenceSha256': RECEIPT_SHA256,
            'confirmationDatasetSha256': panel_hash,
            'scoringScheduleSha256': digest([sample.request for sample in samples]),
            'absoluteGate': {'caseIdsByTask': probes, 'minimumExactPassesPerCase': tested['minimumExactPassesPerProbe']},
            'sourceSha256': {**parent['sourceSha256'], **tested['sourceSha256'], **sources}}
    return groups, plan, prior, samples


class CaseGateFailed(Exception):
    """Stop before a dispatch after a required case has no possible passing completion."""


def score(samples, plan, costs, evaluate):
    gate = plan['absoluteGate']
    probes, minimum = gate['caseIdsByTask'], gate['minimumExactPassesPerCase']
    keys = {(task, case) for task, ids in probes.items() for case in ids}
    candidate = {digest(sample.request): (sample.request['task'], sample.case['id']) for sample in samples
                 if evidence.CANDIDATE in sample.arms and (sample.request['task'], sample.case['id']) in keys}
    remaining = Counter(candidate.values())
    if set(remaining) != keys or any(count != plan['repeats'] for count in remaining.values()):
        raise ValueError('Every case-level check must receive the sealed number of candidate replies')
    passes, grades, failed = Counter(), [], None

    def checked(sample):
        nonlocal failed
        if failed is not None:
            raise CaseGateFailed
        passed = evaluate(sample)
        if type(passed) is not bool:
            raise ValueError('A scored reply requires an exact grade')
        grades.append(passed)
        key = candidate.get(digest(sample.request))
        if key is not None:
            remaining[key] -= 1
            passes[key] += passed
            if remaining[key] + passes[key] < minimum:
                failed = key
        return passed

    try:
        scoring, details = ordered.original.score_until_rejected(samples, plan, costs, checked)
        paired = 'qualified' if scoring['status'] == 'qualified' else 'rejected'
    except CaseGateFailed:
        scoring = {'status': 'rejected-early', 'completePanel': False, 'scoredRequests': len(grades),
                   'scheduledRequests': len(samples), 'scoringScheduleSha256': plan['scoringScheduleSha256'],
                   'scoredOutcomesSha256': digest(grades),
                   'firstUnsentSampleSha256': digest(samples[len(grades)].request)}
        details, paired = {}, 'unmeasured'
    absolute = evidence.absolute_verdict(probes, details.get('holdout'), minimum)
    if failed is not None and not scoring['completePanel']:
        task, case = failed
        absolute = {'status': 'rejected', 'failedCases': {task: [case]}, 'passesByCase': {task: {case: passes[failed]}}}
    return {'scoring': scoring, **details, 'pairedGate': paired, 'absoluteVerdict': absolute,
            'qualified': paired == absolute['status'] == 'qualified'}


def run(seal, directory, respond, *, delivery, development):
    if directory.resolve().is_relative_to(development.resolve()):
        raise ValueError('Confirmation needs a separate fresh archive')
    _, plan, prior, samples = prepare(development)
    if seal != digest(plan) or delivery not in ('fixture', 'model') or version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the current confirmation seal, pinned GEPA, and declared delivery')
    if prior['delivery'] != delivery:
        raise ValueError('Confirmation delivery must match development')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**plan, 'planSha256': seal, 'delivery': delivery})
    with (directory / 'wire.jsonl').open('x') as wire:
        journal = ordered.parent.original.Journal(wire, plan, respond)

        def evaluate(sample):
            return grounded.score(journal.send('paired', sample.request), sample.case['expected'])[0]

        try:
            outcome = score(samples, plan, prior['searchCosts'], evaluate)
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None
    if journal.physical['qualification'] != outcome['scoring']['scoredRequests']:
        raise ValueError('The journal must end at the recorded scoring cutoff')
    result = {'planSha256': seal, 'delivery': delivery, 'physicalCallsByRole': dict(journal.physical), **outcome}
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay needs a separate fresh archive')
    snapshot = archive_bytes(directory)
    metadata = grounded.load_json(snapshot['plan.json'])
    remaining = iter(snapshot['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        sent, received = next(remaining, None), next(remaining, None)
        if sent is None or received is None:
            raise ValueError('The confirmation journal has an incomplete reply')
        intent, reply = grounded.load_json(sent), grounded.load_json(received)
        if intent != {'sequence': sequence, 'arm': 'paired', 'request': request} or reply['sequence'] != sequence:
            raise ValueError('The confirmation request differs from exact replay')
        return reply['response']

    result = run(metadata['planSha256'], fresh, respond, delivery=metadata['delivery'], development=development)
    if next(remaining, None) is not None or any(archive_bytes(path) != snapshot for path in (directory, fresh)):
        raise ValueError('The confirmation archive differs from exact replay')
    return result


def fixture(groups, plan, profile, case_id=None):
    inherited = ordered.fixture_responder(groups, 'qualifying')
    probes = plan['absoluteGate']['caseIdsByTask']
    translated = {evidence.permute(task, row['input']): (task, row) for task, regions in groups.items()
                  for row in regions['confirmation'] if row['id'] in probes[task]}
    eligible = {row['id'] for _, row in translated.values()}
    if profile not in PROFILES or (case_id is not None and (case_id not in eligible or profile != 'shared-failure')):
        raise ValueError('Use a declared fixture profile and, for shared failure, a reordered case')
    target = case_id or sorted(eligible)[0]

    def respond(request):
        if request['input'] not in translated:
            return inherited(request)
        task, row = translated[request['input']]
        if (profile == 'shared-failure' and row['id'] == target) or (
                profile == 'single-miss' and request['repeat'] == 0):
            return json.dumps(evidence.coverage.mutation(task, row['expected']), sort_keys=True)
        return inherited({**request, 'input': row['input']})

    return respond


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development', type=Path, required=True)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--fixture', metavar='PLAN_SHA256')
    modes.add_argument('--replay', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=PROFILES, default='qualifying')
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out):
        parser.error('Fixture and replay require a fresh output directory')
    if args.replay:
        result = replay(args.replay, args.out, development=args.development)
    else:
        groups, plan, _, _ = prepare(args.development)
        result = (run(args.fixture, args.out, fixture(groups, plan, args.profile), delivery='fixture',
                      development=args.development) if args.fixture else {**plan, 'planSha256': digest(plan)})
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
