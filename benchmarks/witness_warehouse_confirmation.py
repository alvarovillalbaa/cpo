"""Rehearse balanced warehouse confirmation against a qualifying development archive."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import grounded, grounded_staged as staged, grounded_witness_halving_futility as original
from benchmarks import typed_policy, witness_regime_coverage as coverage
from cpo._contract import digest


archive_bytes = original.parent.original.archive_bytes


def prepare(development):
    groups, inherited, prior = original.prepare(development)
    if inherited['developmentPlanSha256'] != coverage.bound.PORTABLE:
        raise ValueError('Use a qualifying archive from the exact published development plan')
    added = coverage.stress_cases(groups, (typed_policy.cohorts(grounded.SEED), staged.cohorts()))
    panel = coverage.balanced_confirmation(groups, added)
    previous = {row['id'] for row in groups['warehouse']['confirmation']}
    sentinels = [row['id'] for row in panel if row['id'] not in previous]
    if len(sentinels) != 6:
        raise ValueError('The coverage amendment must introduce the six missing warehouse regimes')
    groups['warehouse']['confirmation'] = panel
    samples = original.scoring_schedule(groups, prior['selected'], 'confirmation')
    if len(samples) != inherited['requestCeiling']:
        raise ValueError('The confirmation schedule must retain the inherited request ceiling')

    names = (Path(__file__), Path(coverage.__file__))
    plan = {**inherited, 'protocol': 'portable-grounded-witness-warehouse-confirmation-v1',
            'parentConfirmationPlanSha256': digest(inherited),
            'confirmationDatasetSha256': digest({task: rows['confirmation'] for task, rows in groups.items()}),
            'confirmationScheduleSha256': digest([sample.request for sample in samples]),
            'absoluteGate': {'warehouseCaseIds': sentinels, 'minimumPassesPerCase': 1},
            'sourceSha256': {**inherited['sourceSha256'], **{
                path.resolve().relative_to(original.ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                for path in names}}}
    return groups, plan, prior, samples


def absolute_verdict(plan, observed):
    if observed is None:
        return {'status': 'unmeasured'}
    gate = plan['absoluteGate']
    counts = dict.fromkeys(gate['warehouseCaseIds'], 0)
    for reply in observed['warehouse']:
        if reply['id'] in counts:
            counts[reply['id']] += reply['passes'][original.parent.CANDIDATE]
    failed = [case for case, passes in counts.items() if passes < gate['minimumPassesPerCase']]
    return {'status': 'rejected' if failed else 'qualified', 'passesByCase': counts, 'failedCases': failed}


def run(seal, directory, respond, *, development):
    _, plan, prior, samples = prepare(development)
    if (seal != digest(plan) or prior['delivery'] != 'fixture' or version('gepa') != plan['gepaVersion']
            or directory.resolve().is_relative_to(development.resolve())):
        raise ValueError('Use the current seal, pinned GEPA, and a separate qualifying fixture')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**plan, 'planSha256': seal, 'delivery': 'fixture'})
    with (directory / 'wire.jsonl').open('x') as wire:
        journal = original.parent.original.Journal(wire, plan, respond)

        def evaluate(sample):
            text = journal.send('paired', sample.request)
            return grounded.score(text, sample.case['expected'])[0]

        try:
            scoring, outcome = original.score_until_rejected(samples, plan, prior['searchCosts'], evaluate)
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None
    if journal.physical['qualification'] != scoring['scoredRequests']:
        raise ValueError('The journal differs from the completed scoring prefix')
    absolute = absolute_verdict(plan, outcome.get('holdout'))
    comparative = scoring['status'] == 'qualified'
    result = {'planSha256': seal, 'delivery': 'fixture', 'scoring': scoring, **outcome, 'absoluteVerdict': absolute,
              'comparativeQualified': comparative, 'qualified': comparative and absolute['status'] == 'qualified'}
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate output directory')
    original_archive = archive_bytes(directory)
    seal = grounded.load_json(original_archive['plan.json'])['planSha256']
    remaining = iter(original_archive['wire.jsonl'].splitlines())
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

    result = run(seal, fresh, respond, development=development)
    if next(remaining, None) is not None or any(archive_bytes(path) != original_archive for path in (fresh, directory)):
        raise ValueError('The confirmation archive differs from exact replay')
    return result


def fixture(groups, plan, profile):
    inherited = original.fixture_responder(groups, 'qualifying')
    sentinel = next(row for row in groups['warehouse']['confirmation']
                    if row['id'] == plan['absoluteGate']['warehouseCaseIds'][0])
    wrong = json.dumps(coverage.mutation('warehouse', sentinel['expected']), sort_keys=True)

    def respond(request):
        if profile == 'faulted-scoring':
            return '{}'
        if (request['input'] == sentinel['input'] and (profile == 'shared-rule-error' or
                (profile == 'single-miss' and request['repeat'] == 0))):
            return wrong
        return inherited(request)

    return respond


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--development', type=Path, required=True)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--fixture', metavar='PLAN_SHA256')
    actions.add_argument('--replay', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=('qualifying', 'shared-rule-error', 'single-miss', 'faulted-scoring'),
                        default='qualifying')
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out):
        parser.error('Fixture and replay require a fresh output directory')
    if args.replay:
        result = replay(args.replay, args.out, development=args.development)
    else:
        groups, plan, _, _ = prepare(args.development)
        if args.fixture:
            result = run(args.fixture, args.out, fixture(groups, plan, args.profile), development=args.development)
        else:
            result = {**plan, 'planSha256': digest(plan)}
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
