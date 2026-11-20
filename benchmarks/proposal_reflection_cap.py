"""Measure an eight-case proposal screen with a hard reflection cap."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks import proposal_short_validation as short
from benchmarks.case_difficulty_allocation import checked_file
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest


REFERENCE = '8ef8592823199c56a562fe115431df2b4a1ea83159a3f85062aa1fed0910465c'
LIMITS = {'short-8-r0': 0, 'short-8-r1': 1, 'short-8-r2': 2}
CAPS = (short.CAP, 'short-8', *LIMITS, 171)
CONTROLS = (*source.continuous.GEPA, 'cpo-72', 'cpo-171', 'cpo-short-8')


def bounded_search(core, maximum):
    def search(initial, train, validation, evaluate, propose, *, rounds, opening_pair, **options):
        if opening_pair is None:
            raise ValueError('The capped search requires the precomputed opening')
        calls = 0

        def reflect(*args):
            nonlocal calls
            if calls == maximum:
                raise ValueError('Search exceeded its reflection cap')
            calls += 1
            return propose(*args)

        result = core(initial, train, validation, evaluate, reflect,
                      rounds=min(rounds, maximum + 1), opening_pair=opening_pair, **options)
        if result.reflections != calls:
            raise ValueError('Search reflection accounting disagrees with the callback journal')
        return result

    return search


def measure(plan, panels, references, previous):
    original = source.proposal_episode
    continuous = source.continuous
    step = continuous.step
    gepa = import_module('gepa.optimize_anything')
    optimize = gepa.optimize_anything
    callbacks = Counter({arm: 0 for arm in continuous.GEPA})

    def episode(matrix, start, layouts, settings):
        arm = settings['evaluationLookupLimit']
        if arm not in LIMITS and arm != 'short-8':
            return original(matrix, start, layouts, settings)
        settings = {**settings, 'evaluationLookupLimit': short.CAP}
        if arm == 'short-8':
            return short.archive_episode(matrix, start, layouts, settings, width=8)
        with patch.object(cycle, 'search', bounded_search(cycle.search, LIMITS[arm])):
            return short.archive_episode(matrix, start, layouts, settings, width=8)

    def traced_step(arm, *args, **options):
        if arm not in continuous.GEPA:
            return step(arm, *args, **options)

        def traced_optimize(*optimize_args, config, **optimize_options):
            proposer = config.reflection.custom_candidate_proposer

            def count(*propose_args, **propose_options):
                callbacks[arm] += 1
                return proposer(*propose_args, **propose_options)

            with patch.object(config.reflection, 'custom_candidate_proposer', count):
                return optimize(*optimize_args, config=config, **optimize_options)

        with patch.object(gepa, 'optimize_anything', traced_optimize):
            return step(arm, *args, **options)

    with (patch.multiple(source, CAPS=CAPS, proposal_episode=episode),
          patch.object(continuous, 'step', traced_step)):
        report = source.measure_phase(plan, panels, references)
    for name, points in report['panels'].items():
        if any(points[label] != previous[name][label] for label in CONTROLS):
            raise ValueError(f'An unchanged control differs from its published trace for {name}')
    report['gepaProposerCallbacks'] = dict(callbacks)
    return report


def prepare():
    parent, phases, _ = short.prepare()
    frozen = checked_file('docs/proposal-short-validation-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The previous validation benchmark changed')
    design = {'protocol': 'cpo-proposal-reflection-cap-v1', 'referenceReportSha256': REFERENCE,
              'searchCap': short.CAP, 'screenWidth': 8, 'reflectionLimits': LIMITS,
              'primary': 'cpo-short-8-r1', 'primaryCohort': parent['primaryCohort'],
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'gate': parent['gate'],
              'scope': ('Keep the precomputed opening and complete both sides of validation. Allow up to one '
                        'subsequent reflection in the primary arm. Measure both official GEPA proposer callbacks.')}
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
