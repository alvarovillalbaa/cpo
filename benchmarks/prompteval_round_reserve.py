"""Measure where the search budget goes and compare built-in round reserves."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_archive_cycles as archive, prompteval_continuous as continuous
from benchmarks import prompteval_transfer as transfer
from cpo import cycle
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
POLICIES = ('base', 'runner-up')
CAPS = (88, 171)
RESERVES = ('adaptive', 'fixed-round')
SOURCE_REPORT_SHA256 = '4af1cc484206ea6ac351e177ef427c4397281c074c6bd9cd015fc235c404c274'


def attributed_step(upstream, method, matrix, incumbent, layout, plan, *, fixed_round):
    paid = set()
    role = {case: name for name in ('train', 'validation') for case in layout[name]}
    original_cpo, original_gepa = cycle.search, transfer.optimize_gepa

    def measured_cpo(initial, train, validation, evaluate, propose, **settings):
        def observe(prompt, row):
            paid.add((prompt, int(row.id)))
            return evaluate(prompt, row)

        if fixed_round:
            settings['adaptive'] = False
        return original_cpo(initial, train, validation, observe, propose, **settings)

    def measured_gepa(initial, alternatives, train, validation, evaluate, **settings):
        def observe(prompt, case):
            paid.add((prompt, case))
            return evaluate(prompt, case)

        return original_gepa(initial, alternatives, train, validation, observe, **settings)

    with patch.object(cycle, 'search', measured_cpo), patch.object(transfer, 'optimize_gepa', measured_gepa):
        result = upstream(method, matrix, incumbent, layout, plan)
    if len(paid) != result['searchLookups'] or any(case not in role for _, case in paid):
        raise ValueError('Observed search calls do not reconcile by role')
    counts = Counter(role[case] for _, case in paid)
    validation_counts = Counter(prompt for prompt, case in paid if role[case] == 'validation')
    incumbent_calls = validation_counts.pop(incumbent, 0)
    complete = sum(count for count in validation_counts.values() if count == len(layout['validation']))
    incomplete = sum(count for count in validation_counts.values() if count < len(layout['validation']))
    return {**result, 'searchByRole': dict(counts), 'validationByCandidate': {
        'incumbent': incumbent_calls, 'completeChallenger': complete, 'partialChallenger': incomplete}}


def attributed_episode(matrix, held, seed, original, reserve):
    upstream = continuous.step

    def step(method, contents, incumbent, layout, plan):
        return attributed_step(upstream, method, contents, incumbent, layout, plan,
                               fixed_round=reserve == 'fixed-round')

    with patch.object(archive, 'POLICIES', POLICIES), patch.object(continuous, 'step', step):
        return archive.episode(matrix, held, seed, original)


def summarize(episodes):
    with patch.object(archive, 'POLICIES', POLICIES):
        result = archive.summarize(episodes)
    breakdown, by_candidate = {}, {}
    for method in result['totals']:
        calls = Counter(train=0, validation=0, qualification=0)
        validation = Counter(incumbent=0, completeChallenger=0, partialChallenger=0)
        for episode in episodes:
            for step in episode[method]['steps']:
                calls.update(step.get('searchByRole', {}))
                calls['qualification'] += step['qualificationLookups']
                validation.update(step.get('validationByCandidate', {}))
        expected = result['totals'][method]
        if (calls['train'] + calls['validation'] != expected['searchLookups'] or
                calls['qualification'] != expected['qualificationLookups'] or sum(validation.values()) != calls['validation']):
            raise ValueError('Search and qualification charges differ from the recorded totals')
        breakdown[method] = calls
        by_candidate[method] = validation
    return {**result, 'callsByRole': breakdown, 'validationByCandidate': by_candidate,
            'episodeTraceSha256': digest(episodes)}


def prepare(phase, cap):
    parent, original, _, source = archive.prepare(phase, cap)
    report = (ROOT / 'docs/prompteval-archive-cycles-results-v1.json').read_bytes()
    if sha256(report).hexdigest() != SOURCE_REPORT_SHA256:
        raise ValueError('Published archive replay differs from the verified source')
    cases = json.loads(report, object_pairs_hook=unique_object)
    published = next(run for run in cases['runs'] if run['phase'] == phase and run['searchCap'] == cap)
    if digest(parent) != published['planSha256']:
        raise ValueError('Archive replay plan differs from the verified source')
    plan = {'protocol': 'cpo-prompteval-round-reserve-v1', 'phase': phase, 'searchCap': cap,
            'parentPlanSha256': published['planSha256'], 'parentReportSha256': published['reportSha256'],
            'publishedSummarySha256': SOURCE_REPORT_SHA256, 'gepaVersion': original['gepaVersion'],
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'policies': list(POLICIES),
            'reserves': list(RESERVES), 'fixedRoundBehavior': 'CPO search with adaptive=False and the same proposal order'}
    return plan, original, source, published['panels']


def replay(plan, original, source, published):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        results = {reserve: summarize([attributed_episode(matrix, held, seed, original, reserve)
                                       for seed in original['seeds']]) for reserve in RESERVES}
        adaptive, fixed = (results[reserve]['totals'] for reserve in RESERVES)
        keys = ('holdoutPasses', 'searchLookups', 'qualificationLookups', 'promotions')
        for arm, totals in adaptive.items():
            if [totals[key] for key in keys] != published[name]['totals'][arm]:
                raise ValueError('The measured adaptive baseline differs from the published result')
            if arm.startswith('gepa-') and totals != fixed[arm]:
                raise ValueError('Changing the CPO reserve affected the GEPA control')
        panels[name] = results
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=archive.PHASES, required=True)
    parser.add_argument('--cap', type=int, choices=CAPS, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, source, published = prepare(args.phase, args.cap)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA benchmark dependency')
    report = replay(plan, original, source, published)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
