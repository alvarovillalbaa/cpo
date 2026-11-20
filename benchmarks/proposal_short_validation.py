"""Compare short proposal search panels with full evidence before nomination."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks import proposal_qualification_veto as precedent
from benchmarks.case_difficulty_allocation import checked_file
from cpo import expected_cost_proposal_cycle as cycle
from cpo._contract import digest


REFERENCE = '0c0cd4fdfc467bc5c320962db12a2d3d270d1b3797fa03d8a3f7b72aa1b91792'
CAP = 72
POLICIES = {'short-8': 8, 'short-12': 12, 'short-16': 16}
CAPS = (CAP, *POLICIES, 171)


def short_search(width, counts):
    core = cycle.search

    def search(initial, train, validation, evaluate, propose, *, metric_limit, **options):
        prefix, suffix = validation[:width], validation[width:]
        if not 0 < width < len(validation) or metric_limit < 2 * len(validation):
            raise ValueError('The shortlist requires a proper prefix and enough lookups to finish a pair')
        if options.get('field_credit') or any(row.critical for row in validation):
            raise ValueError('This replay requires noncritical binary validation')
        ledger = {}

        def read(prompt, row):
            key = prompt, row.id
            if key not in ledger:
                if len(ledger) == metric_limit:
                    raise ValueError('The search exceeded its paid lookup ceiling')
                ledger[key] = evaluate(prompt, row)
            return ledger[key]

        result = core(initial, train, prefix, read, propose, metric_limit=metric_limit - 2 * len(suffix), **options)
        if len(ledger) != result.evaluations:
            raise ValueError('Shortlist accounting differs from the search journal')
        nominee = result.prompt
        counts.update(screenLookups=len(ledger), screenCandidates=len(result.events) - 1,
                      prefixPerfect=int(len(result.events[0]['passed']) == width))
        if nominee == initial:
            return result
        gain = sum(read(nominee, row).passed - read(initial, row).passed for row in validation)
        counts.update(screenNominees=1, completionLookups=len(ledger) - result.evaluations,
                      fullPanelRejections=int(gain <= 0))
        return replace(result, prompt=nominee if gain > 0 else initial, evaluations=len(ledger))

    return search


def archive_episode(matrix, start, layouts, plan, *, width):
    incumbent, total, trace = start, Counter(), []
    with patch.object(cycle, 'search', short_search(width, total)):
        for layout in layouts:
            result, _, search_hash = source.archive_step(matrix, incumbent, layout, plan)
            replies = () if result.qualification is None else result.qualification.observations
            total.update(searchLookups=result.search.evaluations, expected=len(replies),
                         promotions=int(result.promoted), reflections=result.search.reflections)
            trace.append((incumbent, result.search.prompt, result.prompt, search_hash,
                          [(item.prompt, item.row_id, item.repeat, item.passed) for item in replies]))
            incumbent = result.prompt
    return int(incumbent), total, trace


def replay(plan, panels, references, previous):
    original = source.proposal_episode

    def episode(matrix, start, layouts, settings):
        width = POLICIES.get(settings['evaluationLookupLimit'])
        if width is None:
            return original(matrix, start, layouts, settings)
        return archive_episode(matrix, start, layouts, {**settings, 'evaluationLookupLimit': CAP}, width=width)

    with patch.multiple(source, CAPS=CAPS, proposal_episode=episode):
        report = source.measure_phase(plan, panels, references)
    for name, points in report['panels'].items():
        if any(points[label] != previous[name][label] for label in (*source.continuous.GEPA, 'cpo-72', 'cpo-171')):
            raise ValueError(f'An unchanged budget control differs from its published trace for {name}')
    return report


def published_controls(previous):
    references = {}
    for name, panel in previous.items():
        totals = {label: {key: panel[label][key] for key in
                          ('holdoutPasses', 'searchLookups', 'qualificationLookups', 'promotions')}
                  for label in source.continuous.GEPA}
        cpo = panel['cpo-171']
        totals[source.continuous.CPO[0]] = {key: cpo[key] for key in ('holdoutPasses', 'searchLookups', 'promotions')}
        totals[source.continuous.CPO[0]]['qualificationLookups'] = cpo['full']
        references[name] = {'totals': totals}
    return references


def prepare():
    parent, phases, _, independent_plan, archive = precedent.prepare()
    frozen = checked_file('docs/proposal-qualification-veto-results-v1.json', REFERENCE)
    if digest(parent) != frozen['designSha256']:
        raise ValueError('The previous proposal replay changed')
    previous = frozen['results']
    independent = precedent.INDEPENDENT
    phases[independent] = independent_plan, archive['panels'], published_controls(previous[independent]['panels'])
    design = {'protocol': 'cpo-proposal-short-validation-v1', 'referenceReportSha256': REFERENCE,
              'searchCap': CAP, 'screenWidths': POLICIES, 'primary': 'cpo-short-12',
              'primaryCohort': independent, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': ('Screen on the seeded validation prefix, reserve the cost to finish both members of the final '
                        'pair, and require strict full-panel improvement before the original independent qualification.'),
              'gate': 'Joint paired 95 percent lower endpoint above zero and paid cost at or below both GEPA modes.'}
    return design, phases, previous


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
    results = {phase: replay(*inputs, previous[phase]['panels']) for phase, inputs in phases.items()}
    primary = results[design['primaryCohort']]
    comparison = primary['pairedComparisons'][design['primary']]
    primary['primaryPassed'] = (comparison['jointPairedRange95'][0] > 0
                                and max(comparison['lookupDelta'].values()) <= 0)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
