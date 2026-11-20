"""Verify an early dispatch stop against the portable grounded comparison."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import grounded, grounded_fixture
from cpo._contract import digest
from cpo.development_qualification import Sample, run_development_qualification


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ('unchanged', 'ticket-fails', 'shared-prompts')


def plan():
    parent = grounded.plan()
    paths = ('benchmarks/development_qualification.py', 'cpo/development_qualification.py', *parent['sourceSha256'])
    return {'protocol': 'cpo-development-qualification-fixture-v1', 'priorPlanSha256': digest(parent),
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'gepaVersion': parent['gepaVersion'], 'profiles': PROFILES,
            'gate': {'minimumPassesPerTask': parent['holdoutMinimumPerTask'],
                     'minimumAddedPasses': parent['minimumAdditionalPasses'],
                     'maxSearchCostPercentForEfficiency': parent['maximumSearchCallPercentForEfficiency']}}


def requests(groups, selected):
    for task in grounded.TASKS:
        order = Random(f'{grounded.SEED}:{task}:holds')
        for case in groups[task]['holdout']:
            for repeat in range(grounded.REPEATS):
                arms = list(selected[task])
                order.shuffle(arms)
                shared = {}
                for arm in arms:
                    shared.setdefault(selected[task][arm], []).append(arm)
                for prompt, matched in shared.items():
                    yield Sample(task, case['id'], repeat, case['critical'], tuple(matched)), prompt, case


def run_profile(profile, settings, groups, baseline):
    selected, costs = baseline['selected'], baseline['searchCallsByArm']
    if profile == 'shared-prompts':
        selected = {task: dict.fromkeys(prompts, prompts['cpo']) for task, prompts in selected.items()}
        costs = dict.fromkeys(costs, 100)
    planned = tuple(requests(groups, selected))
    schedule = tuple(sample for sample, _, _ in planned)

    def reply(entry):
        sample, prompt, case = entry
        if profile == 'ticket-fails' and sample.task == 'ticket' and 'cpo' in sample.arms:
            return False
        text = grounded_fixture.respond({'task': sample.task, 'role': 'qualification',
                                         'instruction': prompt, 'input': case['input'], 'repeat': sample.repeat})
        return grounded.score(text, case['expected'])[0]

    if profile == 'unchanged':
        expected = [(req['task'], req['repeat'], req['instruction'], req['input'])
                    for item in baseline['journal'] if (req := item['request'])['role'] == 'qualification']
        actual = [(s.task, s.repeat, prompt, row['input']) for s, prompt, row in planned]
        if expected != actual:
            raise ValueError('The planned samples differ from the published paired fixture order')

    pending = iter(planned)

    def observe(sample):
        entry = next(pending)
        if entry[0] != sample:
            raise ValueError('Qualification dispatched outside the planned prefix')
        return reply(entry)

    stopped = run_development_qualification(schedule, observe, gate=settings['gate'], search_costs=costs)
    # Run the full panel independently to compare the verdict.
    outcomes = {task: {} for task in groups}
    full = tuple(map(reply, planned))
    for sample, passed in zip(schedule, full, strict=True):
        cell = outcomes[sample.task].setdefault((sample.case, sample.repeat), (sample.critical, {}))
        cell[1].update(dict.fromkeys(sample.arms, passed))
    verdict = grounded.verdict(outcomes, costs, grounded.plan())
    count = len(stopped.observations)
    if ((stopped.status == 'qualified') != verdict['qualified'] or stopped.observations != full[:count]
            or stopped.status == 'qualified' and count != len(full)):
        raise ValueError('The dispatch stop changed the computed development verdict')
    return {'status': stopped.status, 'paidQualificationReplies': count, 'plannedQualificationReplies': len(full),
            'omittedQualificationReplies': len(full) - count, 'reasons': stopped.reasons,
            'paidPrefixSha256': digest(stopped.observations), 'fullFixtureVerdict': verdict['qualified']}


def replay(settings):
    groups = grounded.cohorts(grounded.SEED)
    baseline = grounded.run(grounded_fixture.respond, delivery='fixture')
    results = {profile: run_profile(profile, settings, groups, baseline) for profile in settings['profiles']}
    return {'plan': settings, 'planSha256': digest(settings), 'delivery': 'fixture', 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    settings = plan()
    seal = digest(settings)
    if args.execute is None and args.out is None:
        print(json.dumps({**settings, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != settings['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(settings)
    with args.out.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
