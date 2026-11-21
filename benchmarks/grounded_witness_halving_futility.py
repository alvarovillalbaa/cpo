"""Stop the prospective fallback benchmark when its paired gate cannot pass."""

import argparse
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import grounded, grounded_staged as staged, grounded_witness_halving as parent
from cpo._contract import digest


ROOT = parent.ROOT
PARENT_SEAL = 'a051692499b42db79f93ae2d7a5b5e4c3845b16c915a8238791d814af3567bca'
ARMS = parent.ARMS


@dataclass(frozen=True)
class Sample:
    request: dict
    case: dict
    arms: tuple[str, ...]


def prepare(development=None):
    groups, original, _ = parent.prepare()
    if digest(original) != PARENT_SEAL:
        raise ValueError('The public fallback protocol must reproduce before adding futility')
    runner = Path(__file__).resolve()
    plan = {**original, 'protocol': 'portable-grounded-witness-halving-futility-development-v1',
            'parentPlanSha256': PARENT_SEAL,
            'sourceSha256': {**original['sourceSha256'],
                             runner.relative_to(ROOT).as_posix(): sha256(runner.read_bytes()).hexdigest()},
            'scoringRule': ('Keep the paired schedule and exact grader. Reject before the next call only if the '
                            'most favorable completion fails at least one gate. A pass needs a complete panel.')}
    if development is None:
        return groups, plan, None

    archive = parent.original.archive_bytes(development)
    with TemporaryDirectory(prefix='cpo-halving-futility-bind-') as tmp:
        prior = replay(development, Path(tmp) / 'verified')
    if (not prior['qualifiedOnBothMeasures'] or not prior['scoring']['completePanel'] or
            parent.original.archive_bytes(development) != archive):
        raise ValueError('Confirmation requires an exact, complete, qualifying development archive')
    cap = len(scoring_schedule(groups, prior['selected'], 'confirmation'))
    plan.update(protocol='portable-grounded-witness-halving-futility-confirmation-v1',
                gate=parent.original.CONFIRMATION_GATE, logicalLimitsByRole={'qualification': cap},
                physicalLimitsByRole={'qualification': cap}, requestCeiling=cap,
                developmentPlanSha256=prior['planSha256'], developmentDelivery=prior['delivery'],
                developmentArchiveSha256={name: sha256(raw).hexdigest() for name, raw in archive.items()},
                selectedSha256=digest(prior['selected']))
    return groups, plan, prior


def scoring_schedule(groups, selected, split):
    samples = []
    for task, regions in groups.items():
        rows = {row['input']: row for row in regions[split]}
        schema = staged.schema(regions)
        prompts = selected[task]

        def collect(_arm, role, prompt, inputs, *, repeat):
            request = {'task': task, 'role': role, 'instruction': prompt, 'input': inputs,
                       'jsonSchema': schema, 'repeat': repeat}
            samples.append(Sample(request, rows[inputs], tuple(arm for arm, value in prompts.items() if value == prompt)))
            return '{}'

        grounded.qualify_task(task, regions[split], prompts, collect)
    return samples


def score_until_rejected(samples, plan, costs, evaluate):
    """Verify the exact existing gate under its most favorable shared completion."""
    if not samples or not costs:
        raise ValueError('Futility needs a sealed schedule and fixed search costs')
    cells, visit, grades = {}, [], []
    for sample in samples:
        case = sample.case
        task = cells.setdefault(sample.request['task'], {})
        repeat = sample.request['repeat']
        cell = task.setdefault((case['id'], repeat), {'id': case['id'], 'repeat': repeat,
                                                     'critical': case['critical'], 'passes': {}})
        visit.append(cell['passes'])
        cell['passes'].update(dict.fromkeys(sample.arms, parent.CANDIDATE in sample.arms))
    optimistic = {task: list(rows.values()) for task, rows in cells.items()}
    for sample, passes in zip(samples, visit, strict=True):
        verdicts = parent.finish(plan, optimistic, costs)
        if not all(verdict['qualified'] for verdict in verdicts.values()):
            break
        passed = evaluate(sample)
        if type(passed) is not bool:
            raise ValueError('A scored reply requires an exact grade')
        grades.append(passed)
        passes.update(dict.fromkeys(sample.arms, passed))

    complete = len(grades) == len(samples)
    if complete:
        verdicts = parent.finish(plan, optimistic, costs)
    scoring = {'status': ('qualified' if all(verdict['qualified'] for verdict in verdicts.values()) else 'rejected')
                         if complete else 'rejected-early',
               'completePanel': complete, 'scoredRequests': len(grades), 'scheduledRequests': len(samples),
               'scoringScheduleSha256': digest([sample.request for sample in samples]),
               'scoredOutcomesSha256': digest(grades)}
    if complete:
        return scoring, {'holdout': optimistic, 'verdicts': verdicts}
    scoring['firstUnsentSampleSha256'] = digest(samples[len(grades)].request)
    return scoring, {'verdictsOnBestCompletion': verdicts}


def run(seal, directory, respond, *, delivery, development=None):
    groups, plan, prior = prepare(development)
    if seal != digest(plan) or delivery not in ('fixture', 'model') or version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the sealed futility comparison, pinned GEPA, and declared delivery')
    if prior and (prior['delivery'] != delivery or directory.resolve().is_relative_to(development.resolve())):
        raise ValueError('Confirmation needs matching delivery and a separate fresh archive')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**plan, 'planSha256': seal, 'delivery': delivery})
    selected, admissions, counts = ({}, {}, {}) if prior is None else (
        prior['selected'], prior['admissions'], prior['additionalValidationUses'])
    split = 'holdout' if prior is None else 'confirmation'
    with (directory / 'wire.jsonl').open('x') as wire:
        journal = parent.original.Journal(wire, plan, respond)
        try:
            if prior is None:
                for task, regions in groups.items():
                    search = {name: regions[name] for name in ('train', 'validation', 'admission')}
                    validation = {row['input'] for row in search['validation']}
                    training = {row['input'] for row in search['train']}
                    admission = {row['input'] for row in search['admission']}
                    schema = staged.schema(regions)

                    def dispatch(arm, role, prompt, inputs, *, repeat=None):
                        request = {'task': task, 'role': role, 'instruction': prompt, 'input': inputs}
                        if role != 'reflection':
                            allowed = validation | training if arm in parent.original.GEPA else validation
                            if inputs not in {'evaluation': allowed, 'admission': admission}[role]:
                                raise ValueError('Search left its sealed case split')
                            request['jsonSchema'] = schema
                        if repeat is not None:
                            request['repeat'] = repeat
                        return journal.send(arm, request)

                    selected[task], admissions[task], counts[task] = parent.choose(task, search, dispatch, journal)
                uses = {arm: journal.search_uses[arm] for arm in ARMS}
                costs = {'logicalSearchUses': {arm: len(samples) for arm, samples in uses.items()},
                         'attributedSearchRequests': {arm: len(set(samples)) for arm, samples in uses.items()}}
            else:
                costs = prior['searchCosts']

            def evaluate(sample):
                text = journal.send('paired', sample.request)
                return grounded.score(text, sample.case['expected'])[0]

            samples = scoring_schedule(groups, selected, split)
            if len(samples) > plan['physicalLimitsByRole']['qualification'] or (prior and len(samples) != plan['requestCeiling']):
                raise ValueError('The physical scoring schedule differs from its seal')
            scoring, outcome = score_until_rejected(samples, plan, costs, evaluate)
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None
    if journal.physical['qualification'] != scoring['scoredRequests']:
        raise ValueError('The journal must end on the same paid scoring prefix')
    result = {'planSha256': seal, 'delivery': delivery, 'selected': selected, 'admissions': admissions,
              'additionalValidationUses': counts, 'searchCosts': costs, 'qualifiedOnBothMeasures': scoring['status'] == 'qualified',
              'logicalCallsByRole': dict(journal.logical), 'physicalCallsByRole': dict(journal.physical),
              'scoring': scoring, **outcome}
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development=None):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate output directory')
    archive = parent.original.archive_bytes(directory)
    metadata = grounded.load_json(archive['plan.json'])
    pending = iter(archive['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        sent, reply = next(pending, None), next(pending, None)
        if sent is None or reply is None:
            raise ValueError('The journal contains an incomplete reply')
        sent, reply = grounded.load_json(sent), grounded.load_json(reply)
        if sent['sequence'] != sequence or reply['sequence'] != sequence or sent['request'] != request:
            raise ValueError('The replay request differs from the sealed futility journal')
        return reply['response']

    result = run(metadata['planSha256'], fresh, respond, delivery=metadata['delivery'], development=development)
    if next(pending, None) is not None or any(parent.original.archive_bytes(path) != archive for path in (fresh, directory)):
        raise ValueError('The futility archive differs from its exact replay')
    return result


def fixture_responder(groups, profile):
    from benchmarks.grounded_witness_halving_fixture import responder

    inherited = responder(groups, 'rejected' if profile == 'rejected-admission' else 'qualifying')
    if profile != 'faulted-scoring':
        return inherited
    return lambda request: '{}' if request['role'] == 'qualification' else inherited(request)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument('--fixture')
    commands.add_argument('--replay', type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=('qualifying', 'rejected-admission', 'faulted-scoring'), default='qualifying')
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out):
        parser.error('Fixture and replay require a fresh output directory')
    if args.fixture:
        groups = parent.original.cohorts()
        result = run(args.fixture, args.out, fixture_responder(groups, args.profile), delivery='fixture',
                     development=args.development)
    elif args.replay:
        result = replay(args.replay, args.out, development=args.development)
    else:
        _, plan, _ = prepare(args.development)
        result = {**plan, 'planSha256': digest(plan)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
