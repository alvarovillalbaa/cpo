"""Run the witness comparison with the gate-relevant scoring schedule."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded, grounded_staged as staged, grounded_witness_scoring_order as study
from cpo._contract import digest


original = study.original
parent = original.parent
archive_bytes = parent.original.archive_bytes
REFERENCE = 'docs/grounded-witness-scoring-order-results-v1.json'
REFERENCE_SHA256 = 'a938f61a3945f11f1131f1fb7716db35496d8d54943b5e848bcbc375dfa0d094'
PROFILES = ('qualifying', 'rejected-admission', 'outage-scoring-failure')


def prepare(development=None):
    groups, inherited, _ = original.prepare()
    raw = (original.ROOT / REFERENCE).read_bytes()
    receipt = json.loads(raw)
    if (sha256(raw).hexdigest() != REFERENCE_SHA256 or digest(inherited) != study.PARENT_SEAL
            or receipt['plan']['sourceSha256'] != sha256(Path(study.__file__).read_bytes()).hexdigest()):
        raise ValueError('Use the inherited plan and the published scoring-order evidence')
    files = (Path(__file__).resolve(), Path(study.__file__).resolve())
    source = {file.relative_to(original.ROOT).as_posix(): sha256(file.read_bytes()).hexdigest() for file in files}
    plan = {**inherited, 'protocol': 'portable-grounded-witness-ordered-futility-development-v1',
            'parentPlanSha256': study.PARENT_SEAL, 'scoringOrderReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': {**inherited['sourceSha256'], **source}, 'scoringOrder': study.GATE}
    if development is None:
        return groups, plan, None

    snapshots = archive_bytes(development)
    with TemporaryDirectory(prefix='cpo-ordered-witness-bind-') as temporary:
        prior = replay(development, Path(temporary) / 'verified')
    if (archive_bytes(development) != snapshots or not prior['qualifiedOnBothMeasures']
            or not prior['scoring']['completePanel']):
        raise ValueError('Confirmation requires an exact, complete, qualifying ordered development archive')

    samples = study.order(original.scoring_schedule(groups, prior['selected'], 'confirmation'), study.GATE)
    cap = len(samples)
    plan.update(protocol='portable-grounded-witness-ordered-futility-confirmation-v1',
                gate=parent.original.CONFIRMATION_GATE, logicalLimitsByRole={'qualification': cap},
                physicalLimitsByRole={'qualification': cap}, requestCeiling=cap,
                developmentArchiveSha256={name: sha256(data).hexdigest() for name, data in snapshots.items()},
                developmentPlanSha256=prior['planSha256'], developmentDelivery=prior['delivery'],
                selectedSha256=digest(prior['selected']), scoringScheduleSha256=digest([sample.request for sample in samples]))
    return groups, plan, prior


def choose(groups, journal):
    selected, admissions, counts = {}, {}, {}
    for task, regions in groups.items():
        search = {name: regions[name] for name in ('train', 'validation', 'admission')}
        allowed = {name: {case['input'] for case in rows} for name, rows in search.items()}
        schema = staged.schema(regions)

        def dispatch(arm, role, prompt, inputs, *, repeat=None):
            request = {'task': task, 'role': role, 'instruction': prompt, 'input': inputs}
            if role != 'reflection':
                validation = allowed['validation'] | allowed['train'] if arm in parent.original.GEPA else allowed['validation']
                if inputs not in {'evaluation': validation, 'admission': allowed['admission']}[role]:
                    raise ValueError('Search left its sealed case split')
                request['jsonSchema'] = schema
            if repeat is not None:
                request['repeat'] = repeat
            return journal.send(arm, request)

        selected[task], admissions[task], counts[task] = parent.choose(task, search, dispatch, journal)
    uses = {arm: journal.search_uses[arm] for arm in original.ARMS}
    costs = {'logicalSearchUses': {arm: len(requests) for arm, requests in uses.items()},
             'attributedSearchRequests': {arm: len(set(requests)) for arm, requests in uses.items()}}
    return selected, admissions, counts, costs


def run(seal, directory, respond, *, delivery, development=None):
    if development is not None and directory.resolve().is_relative_to(development.resolve()):
        raise ValueError('Confirmation needs a separate fresh archive')
    groups, plan, prior = prepare(development)
    if seal != digest(plan) or delivery not in ('fixture', 'model') or version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the current ordered seal, pinned GEPA, and declared delivery')
    if prior is not None and prior['delivery'] != delivery:
        raise ValueError('Confirmation delivery must match development')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**plan, 'planSha256': seal, 'delivery': delivery})

    with (directory / 'wire.jsonl').open('x') as wire:
        journal = parent.original.Journal(wire, plan, respond)

        def evaluate(sample):
            text = journal.send('paired', sample.request)
            return grounded.score(text, sample.case['expected'])[0]

        try:
            if prior is None:
                selected, admissions, counts, costs = choose(groups, journal)
            else:
                selected, admissions, counts, costs = (prior[key] for key in (
                    'selected', 'admissions', 'additionalValidationUses', 'searchCosts'))
            split = 'holdout' if prior is None else 'confirmation'
            samples = study.order(original.scoring_schedule(groups, selected, split), study.GATE)
            if len(samples) > plan['physicalLimitsByRole']['qualification'] or (prior is not None and (
                    len(samples) != plan['requestCeiling'] or
                    digest([sample.request for sample in samples]) != plan['scoringScheduleSha256'])):
                raise ValueError('The ordered scoring schedule differs from its seal')
            scoring, outcome = original.score_until_rejected(samples, plan, costs, evaluate)
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None
    if journal.physical['qualification'] != scoring['scoredRequests']:
        raise ValueError('The journal must end at the recorded scoring cutoff')
    result = {'planSha256': seal, 'delivery': delivery, 'selected': selected, 'admissions': admissions,
              'additionalValidationUses': counts, 'searchCosts': costs, 'qualifiedOnBothMeasures': scoring['status'] == 'qualified',
              'logicalCallsByRole': dict(journal.logical), 'physicalCallsByRole': dict(journal.physical),
              'scoring': scoring, **outcome}
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development=None):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate output directory')
    snapshot = archive_bytes(directory)
    metadata = grounded.load_json(snapshot['plan.json'])
    remaining = iter(snapshot['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        sent, reply = next(remaining, None), next(remaining, None)
        if sent is None or reply is None:
            raise ValueError('The ordered archive has an incomplete reply')
        intent, received = grounded.load_json(sent), grounded.load_json(reply)
        if intent['sequence'] != sequence or received['sequence'] != sequence or intent['request'] != request:
            raise ValueError('The ordered request differs from the recorded request')
        return received['response']

    result = run(metadata['planSha256'], fresh, respond, delivery=metadata['delivery'], development=development)
    if next(remaining, None) is not None or any(archive_bytes(path) != snapshot for path in (fresh, directory)):
        raise ValueError('The ordered archive differs from exact replay')
    return result


def fixture_responder(groups, profile):
    if profile not in PROFILES:
        raise ValueError('Use a declared fixture profile')
    inherited = original.fixture_responder(groups, 'qualifying' if profile == 'outage-scoring-failure' else profile)
    if profile != 'outage-scoring-failure':
        return inherited
    return lambda request: ('{}' if (request['task'], request['role']) == ('outage', 'qualification')
                            else inherited(request))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument('--fixture', metavar='PLAN_SHA256')
    commands.add_argument('--replay', type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=PROFILES, default='qualifying')
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out):
        parser.error('Fixture and replay require a fresh output directory')
    if args.fixture:
        fixture = fixture_responder(parent.original.cohorts(), args.profile)
        result = run(args.fixture, args.out, fixture, delivery='fixture', development=args.development)
    elif args.replay:
        result = replay(args.replay, args.out, development=args.development)
    else:
        _, plan, _ = prepare(args.development)
        result = {**plan, 'planSha256': digest(plan)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
