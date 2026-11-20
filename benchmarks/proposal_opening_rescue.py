"""Check the unused opening when the short-panel nominee fails full validation."""

import argparse
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks import proposal_opening_pool as precedent
from benchmarks import proposal_reflection_cap as reflections
from benchmarks import proposal_short_validation as short
from benchmarks.case_difficulty_allocation import checked_file
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest
from cpo.pool import select_pool


REFERENCE = '5073e9f876ac2192cbcf0450cc280b4b9549506304ee183abaa786c0018fda09'
POLICIES = ('opening-rescue', 'opening-rescue-screened')
CAPS = (short.CAP, 'short-8-r0', *POLICIES, 171)
CONTROLS = precedent.CONTROLS


def with_rescue(search, counts, *, minimum_prefix_gain=None, width=precedent.SCREEN):
    def run(incumbent, train, validation, evaluate, propose, *, opening_pair, metric_limit, **options):
        paid = {}

        def read(prompt, row):
            key = prompt, row.id
            if key not in paid:
                if len(paid) >= metric_limit:
                    raise ValueError('The opening rescue exceeded its lookup ceiling')
                paid[key] = evaluate(prompt, row)
            return paid[key]

        rejected_before = counts['fullPanelRejections']
        result = search(incumbent, train, validation, read, propose,
                        opening_pair=opening_pair, metric_limit=metric_limit, **options)
        if len(paid) != result.evaluations:
            raise ValueError('The original screen disagrees with the physical lookup ledger')
        if counts['fullPanelRejections'] == rejected_before:
            return result

        openings = (opening_pair.rewrite, opening_pair.repair)
        remaining = [prompt for prompt in openings if any((prompt, row.id) not in paid for row in validation)]
        if result.prompt != incumbent or len(remaining) != 1:
            raise ValueError('The rejected finalist and its sibling must be distinct')
        challenger = remaining[0]
        counts['rescueOpportunities'] += 1
        if len(paid) + sum((challenger, row.id) not in paid for row in validation) > metric_limit:
            counts['unfundedRescues'] += 1
            return result

        if minimum_prefix_gain is not None:
            prefix_gain = sum(read(challenger, row).passed - read(incumbent, row).passed
                              for row in validation[:width])
            if prefix_gain < minimum_prefix_gain:
                counts.update(rescuePrefixRejections=1, rescueLookups=len(paid) - result.evaluations)
                return replace(result, evaluations=len(paid))
        finalist = select_pool((incumbent, challenger), validation, read, metric_limit=metric_limit,
                               adaptive_rejection=True)
        counts.update(rescuesCompared=1, rescueNominations=int(finalist.prompt != incumbent),
                      rescueLookups=len(paid) - result.evaluations)
        return replace(result, prompt=finalist.prompt, evaluations=len(paid))

    return run


def measure(plan, panels, references, previous):
    original = source.proposal_episode
    short_search = short.short_search

    def episode(matrix, start, layouts, settings):
        arm = settings['evaluationLookupLimit']
        if arm not in POLICIES and arm != 'short-8-r0':
            return original(matrix, start, layouts, settings)
        settings = {**settings, 'evaluationLookupLimit': short.CAP}

        def make_screen(width, counters):
            screen = short_search(width, counters)
            if arm == 'short-8-r0':
                return screen
            threshold = 0 if arm == 'opening-rescue-screened' else None
            return with_rescue(screen, counters, minimum_prefix_gain=threshold, width=width)

        with (patch.object(cycle, 'search', reflections.bounded_search(cycle.search, 0)),
              patch.object(short, 'short_search', make_screen)):
            return short.archive_episode(matrix, start, layouts, settings, width=precedent.SCREEN)

    with patch.multiple(source, CAPS=CAPS, proposal_episode=episode):
        report = source.measure_phase(plan, panels, references)
    for name, points in report['panels'].items():
        if any(points[label] != previous[name][label] for label in CONTROLS):
            raise ValueError(f'An unchanged control differs from its published trace for {name}')
    return report


def prepare():
    parent, phases, _ = precedent.prepare()
    frozen = checked_file('docs/proposal-opening-pool-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The previous opening experiment changed')
    design = {'protocol': 'cpo-proposal-opening-rescue-v1', 'referenceReportSha256': REFERENCE,
              'searchCap': short.CAP, 'screenWidth': precedent.SCREEN, 'policies': POLICIES,
              'primary': 'cpo-opening-rescue', 'primaryCohort': parent['primaryCohort'],
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'gate': parent['gate'],
              'scope': ('Preserve successful original nominations. After a full validation rejection, use '
                        'the remaining funded budget to score the other supplied opening. The optional screen '
                        'requires that it at least tie the incumbent on the short prefix.')}
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
