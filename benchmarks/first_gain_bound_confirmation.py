"""Bind and replay the regime confirmation from a qualifying offline fixture."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmarks import first_gain_regime_confirmation as specification
from benchmarks import grounded_witness_halving_futility as scoring
from cpo._contract import digest


development = specification.development
grounded, staged = development.grounded, development.staged
ROOT, ARMS = specification.ROOT, specification.ARMS
FILES = development.parent.FILES
DEVELOPMENT_FILES = (*FILES, development.AUDIT)
SPEC_FILE = 'docs/first-gain-regime-confirmation-v1.json'
SPEC_SHA = 'fc04fc18069c29b0a6539025d050d5f2d7df095b9a86f30bd0522fa13dde3ec1'
PROFILES = ('paired-gain', 'shared-single-miss', 'shared-rule-error')


def snapshot(root, files):
    return {name: (root / name).read_bytes() for name in files}


def schedule(panel, groups, selected, repeats):
    if set(selected) != set(panel) or any(set(prompts) != set(ARMS) for prompts in selected.values()):
        raise ValueError('Confirmation needs the initial prompt and every development finalist')
    layouts = {task: {'train': groups[task]['train'], 'confirmation': rows} for task, rows in panel.items()}
    samples = scoring.scoring_schedule(layouts, selected, 'confirmation')
    assignments = {(task, case['id'], repeat, arm) for task, rows in panel.items() for case in rows
                   for repeat in range(repeats) for arm in ARMS}
    scheduled = [(sample.request['task'], sample.case['id'], sample.request['repeat'], arm)
                 for sample in samples for arm in sample.arms]
    if (len(scheduled) != len(assignments) or set(scheduled) != assignments
            or len({digest(sample.request) for sample in samples}) != len(samples)):
        raise ValueError('The confirmation schedule must cover each arm, case and repeat exactly')
    return samples


def bind(source):
    plan, panel, tasks = specification.prepare()
    raw = (ROOT / SPEC_FILE).read_bytes()
    frozen = grounded.load_json(raw)
    seal = digest(plan)
    if (sha256(raw).hexdigest() != SPEC_SHA or frozen['planSha256'] != seal
            or digest(frozen['plan']) != seal or digest(frozen['rows']) != plan['panelSha256']):
        raise ValueError('The published confirmation panel and gate must reproduce')
    try:
        original = snapshot(source, DEVELOPMENT_FILES)
    except FileNotFoundError as error:
        raise ValueError('Confirmation needs a complete development archive') from error
    manifest = grounded.load_json(original['plan.json'])
    if manifest.get('delivery') != 'fixture' or manifest.get('planSha256') != plan['developmentPlanSha256']:
        raise ValueError('Bind a fixture archive of the exact independent-proposal development seal')
    with TemporaryDirectory(prefix='cpo-first-gain-bind-') as scratch:
        prior, _ = development.replay(source, Path(scratch) / 'replayed')
    if snapshot(source, DEVELOPMENT_FILES) != original or not prior['qualifiedOnBothMeasures']:
        raise ValueError('Confirmation requires unchanged, exactly replayed, qualifying development')
    samples = schedule(panel, tasks, prior['selected'], plan['repeats'])
    if not 0 < len(samples) <= plan['generationRequestCeiling']:
        raise ValueError('The bound schedule exceeds the sealed confirmation ceiling')
    paths = (Path(__file__), Path(scoring.__file__))
    return {
        **plan, 'protocol': 'cpo-first-gain-bound-confirmation-fixture-v1', 'delivery': 'fixture',
        'specificationSha256': seal, 'specificationReceiptSha256': SPEC_SHA,
        'sourceSha256': {**plan['sourceSha256'],
                         **{str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest() for path in paths}},
        'developmentArchiveSha256': {name: sha256(data).hexdigest() for name, data in original.items()},
        'selectedPromptsSha256': digest(prior['selected']), 'developmentSearchCosts': prior['searchCosts'],
        'scheduleSha256': digest([(sample.request, sample.case['id'], sample.arms) for sample in samples]),
        'scheduledRequests': len(samples), 'logicalGrades': sum(len(item.arms) for item in samples),
    }, panel, samples, original


def execute(seal, source, output, respond):
    plan, panel, samples, original = bind(source)
    return _execute(seal, source, output, respond, plan, panel, samples, original)


def _execute(seal, source, output, respond, plan, panel, samples, original):
    if (seal != digest(plan) or output.exists() or output.resolve().is_relative_to(source.resolve())
            or any(part.startswith('live-cpo-luna-') for part in output.resolve().parts)):
        raise ValueError('Use a current seal and a fresh isolated fixture directory')
    if snapshot(source, DEVELOPMENT_FILES) != original:
        raise ValueError('The bound development archive changed before scoring')
    output.mkdir(mode=0o700)
    staged.save(output / 'plan.json', {**plan, 'planSha256': seal})
    outcomes = {task: {} for task in panel}
    with (output / 'wire.jsonl').open('x') as wire:
        envelope = {'physicalLimitsByRole': {'qualification': len(samples)},
                    'logicalLimitsByRole': {'qualification': len(samples)}, 'searchCap': 0,
                    'repeats': plan['repeats']}
        journal = development.parent.shared.Journal(wire, envelope, respond)
        try:
            for sample in samples:
                text = journal.send('paired', sample.request)
                grade, _ = grounded.score(text, sample.case['expected'])
                task, repeat = sample.request['task'], sample.request['repeat']
                replies = outcomes[task].setdefault((sample.case['id'], repeat), {})
                replies.update(dict.fromkeys(sample.arms, grade))
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None
    if (journal.physical['qualification'] != len(samples)
            or snapshot(source, DEVELOPMENT_FILES) != original):
        raise ValueError('The request count or bound development archive changed during scoring')
    verdict = specification.evaluate(plan, panel, outcomes, plan['developmentSearchCosts'])
    result = {'planSha256': seal, 'delivery': 'fixture', 'providerRequests': 0,
              'scoredRequests': len(samples), 'logicalGrades': plan['logicalGrades'], **verdict}
    staged.save(output / 'result.json', result)
    return result


def replay(source, archive, output):
    if output.resolve().is_relative_to(archive.resolve()):
        raise ValueError('Replay needs its own output directory')
    original = snapshot(archive, FILES)
    manifest = grounded.load_json(original['plan.json'])
    if manifest.get('delivery') != 'fixture':
        raise ValueError('Only fixture confirmation archives can be replayed')
    tape = iter(original['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        intent, reply = next(tape, None), next(tape, None)
        if intent is None or reply is None:
            raise ValueError('The confirmation journal has an incomplete reply')
        if grounded.load_json(intent) != {'sequence': sequence, 'arm': 'paired', 'request': request}:
            raise ValueError('The confirmation request differs from exact replay')
        received = grounded.load_json(reply)
        if set(received) != {'sequence', 'response'} or received['sequence'] != sequence:
            raise ValueError('The confirmation reply sequence changed')
        return received['response']

    result = execute(manifest['planSha256'], source, output, respond)
    if next(tape, None) is not None or any(snapshot(path, FILES) != original for path in (archive, output)):
        raise ValueError('The confirmation archive differs from exact replay')
    return result


def qualifying_development(work):
    """Build an explicitly scripted development fixture with a paired holdout gain."""
    tasks, plan = development.prepare()
    seal = digest(plan)
    tied, _ = development.run_fixture(seal, work / 'unqualified')
    if tied['qualifiedOnBothMeasures']:
        raise ValueError('The published tied fixture must remain unqualified')
    missed = {task: {row['input'] for row in [case for case in groups['holdout'] if not case['critical']][:2]}
              for task, groups in tasks.items()}
    answer = development.fixture(tasks)

    def respond(request):
        task = request['task']
        if (request['role'] == 'qualification' and request['input'] in missed[task]
                and request['instruction'] != tied['selected'][task][development.FIRST]):
            return '{}'
        return answer(request)

    output = work / 'qualifying-development'
    with development.configured(tasks, plan):
        qualified = development.parent.run(seal, output, respond, delivery='fixture')
    staged.save(output / development.AUDIT, development.audit(tasks, qualified, output))
    if qualified['selected'] != tied['selected'] or not qualified['qualifiedOnBothMeasures']:
        raise ValueError('The scripted gain must preserve the development path and meet both gates')
    return output


def fixture(plan, panel, samples, profile):
    if profile not in PROFILES:
        raise ValueError('Use a declared confirmation fixture profile')
    by_request = {digest(sample.request): sample for sample in samples}
    paired_gain = {row['id'] for row in [case for case in panel['ticket'] if not case['critical']][:2]}
    sentinel = panel['warehouse'][0]['id']

    def respond(request):
        sample = by_request[digest(request)]
        case = sample.case
        expected = case['expected']
        if case['id'] in paired_gain and plan['candidate'] not in sample.arms:
            expected = specification.coverage.mutation('ticket', expected)
        if case['id'] == sentinel and (profile == 'shared-rule-error' or
                                       (profile == 'shared-single-miss' and request['repeat'] == 0)):
            expected = specification.coverage.mutation('warehouse', expected)
        return json.dumps(expected, sort_keys=True)

    return respond


def verify(work):
    source = qualifying_development(work)
    plan, panel, samples, original = bind(source)
    seal = digest(plan)
    results = {}
    for profile in PROFILES:
        out = work / profile
        result = _execute(seal, source, out, fixture(plan, panel, samples, profile), plan, panel, samples, original)
        if (replay(source, out, work / f'{profile}-replay') != result or not result['pairedGateMet']
                or result['qualified'] != (profile != 'shared-rule-error')):
            raise ValueError('The confirmation fixture differs from its expected gate or exact replay')
        results[profile] = {'scoredRequests': result['scoredRequests'], 'logicalGrades': result['logicalGrades'],
                            'qualified': result['qualified'], 'pairedGateMet': result['pairedGateMet'],
                            'failedRegimeCases': result['failedRegimeCases'],
                            'archiveSha256': {name: sha256(raw).hexdigest()
                                              for name, raw in snapshot(out, FILES).items()}}
    return {'boundPlan': plan, 'planSha256': seal, 'fixtures': results, 'providerRequests': 0}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--verify', action='store_true')
    mode.add_argument('--development', type=Path)
    action = cli.add_mutually_exclusive_group()
    action.add_argument('--fixture', metavar='PLAN_SHA256')
    action.add_argument('--replay', type=Path)
    cli.add_argument('--out', type=Path)
    cli.add_argument('--profile', choices=PROFILES, default='paired-gain')
    args = cli.parse_args()
    writing = args.fixture or args.replay
    if (args.verify and writing) or bool(writing) != bool(args.out):
        cli.error('Fixture and replay require a development archive and a fresh output directory')
    if args.verify:
        with TemporaryDirectory(prefix='cpo-first-gain-confirmation-') as scratch:
            result = verify(Path(scratch))
    elif args.replay:
        result = replay(args.development, args.replay, args.out)
    else:
        plan, panel, samples, original = bind(args.development)
        if args.fixture:
            result = _execute(args.fixture, args.development, args.out, fixture(plan, panel, samples, args.profile),
                              plan, panel, samples, original)
        else:
            result = {**plan, 'planSha256': digest(plan)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
