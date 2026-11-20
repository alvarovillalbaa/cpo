"""Compare both supplied opening proposals without any later reflections."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks import proposal_reflection_cap as reflections
from benchmarks import proposal_short_validation as short
from benchmarks.case_difficulty_allocation import checked_file
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest
from cpo.optimizer import Result
from cpo.pool import select_pool


REFERENCE = '6a4e61353e4101c07cd527f80d28c103b1f7ab592cb1650893428c8470eda701'
POLICIES = ('opening-screened', 'opening-fallback', 'opening-all')
CAPS = (short.CAP, 'short-8-r0', *POLICIES, 171)
SCREEN = 8
CONTROLS = (*source.continuous.GEPA, 'cpo-72', 'cpo-171', 'cpo-short-8-r0')


def opening_pool(policy, counters, *, screen_rows=SCREEN):
    def search(incumbent, _train, validation, evaluate, _propose, *, opening_pair, metric_limit, **_options):
        if opening_pair is None:
            raise ValueError('The opening comparison requires a precomputed pair')
        candidates = (incumbent, opening_pair.rewrite, opening_pair.repair)
        if len(set(candidates)) != 3 or len(validation) < screen_rows or metric_limit < 3 * len(validation):
            raise ValueError('The opening comparison requires a funded pair of distinct challengers')
        paid = {}

        def read(prompt, row):
            key = prompt, row.id
            if key not in paid:
                paid[key] = evaluate(prompt, row)
            return paid[key]

        if policy == 'opening-all':
            eligible = candidates[1:]
        else:
            scores = {prompt: sum(read(prompt, row).passed for row in validation[:screen_rows]) for prompt in candidates}
            eligible = sorted((prompt for prompt in candidates[1:] if scores[prompt] > scores[incumbent]),
                              key=scores.__getitem__, reverse=True)
        counters.update(screenLookups=len(paid), eligibleOpenings=len(eligible), twoEligible=int(len(eligible) == 2))
        if not eligible:
            return Result(incumbent, len(paid), 0, [])
        pools = [(prompt,) for prompt in eligible] if policy == 'opening-fallback' else [eligible]
        for challengers in pools:
            chosen = select_pool((incumbent, *challengers), validation, read, metric_limit=metric_limit,
                                 screen_rows=0 if policy == 'opening-all' else screen_rows, adaptive_rejection=True)
            if chosen.prompt != incumbent:
                counters['repairNominations'] += int(chosen.prompt == opening_pair.repair)
                return Result(chosen.prompt, len(paid), 0, [])
        return Result(incumbent, len(paid), 0, [])

    return search


def archive_episode(matrix, initial, layouts, plan, *, policy):
    incumbent, total, trace = initial, Counter(), []
    with patch.object(cycle, 'search', opening_pool(policy, total)):
        for layout in layouts:
            result, _, search_hash = source.archive_step(matrix, incumbent, layout, plan)
            replies = () if result.qualification is None else result.qualification.observations
            total.update(searchLookups=result.search.evaluations, expected=len(replies),
                         promotions=int(result.promoted), reflections=result.search.reflections)
            trace.append((incumbent, result.search.prompt, result.prompt, search_hash,
                          [(item.prompt, item.row_id, item.repeat, item.passed) for item in replies]))
            incumbent = result.prompt
    return int(incumbent), total, trace


def measure(plan, panels, references, previous):
    original = source.proposal_episode

    def episode(matrix, start, layouts, settings):
        policy = settings['evaluationLookupLimit']
        if policy in POLICIES:
            return archive_episode(matrix, start, layouts, {**settings, 'evaluationLookupLimit': short.CAP},
                                   policy=policy)
        if policy == 'short-8-r0':
            with patch.object(cycle, 'search', reflections.bounded_search(cycle.search, 0)):
                return short.archive_episode(matrix, start, layouts, {**settings, 'evaluationLookupLimit': short.CAP},
                                             width=SCREEN)
        return original(matrix, start, layouts, settings)

    with patch.multiple(source, CAPS=CAPS, proposal_episode=episode):
        report = source.measure_phase(plan, panels, references)
    for name, points in report['panels'].items():
        if any(points[label] != previous[name][label] for label in CONTROLS):
            raise ValueError(f'An unchanged control differs from its published trace for {name}')
    return report


def prepare():
    parent, phases, _ = reflections.prepare()
    frozen = checked_file('docs/proposal-reflection-cap-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The previous reflection budget comparison changed')
    design = {'protocol': 'cpo-proposal-opening-pool-v1', 'referenceReportSha256': REFERENCE,
              'searchCap': short.CAP, 'screenWidth': SCREEN, 'policies': POLICIES, 'primary': 'cpo-opening-screened',
              'primaryCohort': parent['primaryCohort'], 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'gate': parent['gate'],
              'scope': ('Compare both opening candidates on the short panel. Check all eligible challengers '
                        'within the same budget and send only the exact validation winner to qualification.')}
    return design, phases, frozen['results']


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, phases, previous = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for plan, *_ in phases.values()):
        cli.error('Use pinned GEPA 0.1.4')
    results = {phase: measure(*inputs, previous[phase]['panels']) for phase, inputs in phases.items()}
    primary = results[design['primaryCohort']]
    comparison = primary['pairedComparisons'][design['primary']]
    primary['primaryPassed'] = (comparison['jointPairedRange95'][0] > 0
                                and max(comparison['lookupDelta'].values()) <= 0)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
