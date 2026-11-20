"""Give the previous incumbent one chance to qualify again after a promotion."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo._contract import digest


REFERENCE = 'a340fc3fc1ea6757a691ad594a54a13f500adf2d22328db65707e48b9c1289e5'
AUDIT = '878cdb7ac47836ce4a085a3dbef9abe025e8f9ce1f358d8f15d3c8f880f4c3d1'
CAP = 72
POLICIES = ('return', 'vacant')
CAPS = (CAP, *POLICIES, 171)


def archive_episode(matrix, initial, layouts, plan, *, policy):
    incumbent, previous = initial, None
    total, trace = Counter(), []
    for layout in layouts:
        returning = previous if policy == 'return' else None
        if previous is not None:
            # The optimizer skips the incumbent automatically if its ID occupies a proposal slot.
            options = list(layout['alternatives'])
            options[1] = incumbent if returning is None else returning
            layout = {**layout, 'alternatives': options}
        result, _, search_hash = source.archive_step(matrix, incumbent, layout, plan)
        replies = () if result.qualification is None else result.qualification.observations
        promoted = result.prompt != incumbent
        total.update(searchLookups=result.search.evaluations, expected=len(replies),
                     promotions=int(promoted), reflections=result.search.reflections,
                     reservedSlots=int(previous is not None))
        if returning is not None:
            visited = next((event['kind'] for event in result.search.events if event['prompt'] == returning), None)
            nomination = result.search.prompt == returning
            restored = result.prompt == returning
            if restored and (not nomination or not result.promoted or not replies):
                raise ValueError('A return advanced without a fresh paired qualification pass')
            total.update(returnOpened=int(visited is not None), returnValidated=int(visited == 'validated'),
                         returnNominated=int(nomination), returnPromoted=int(restored))
            # Classify opportunities only after the search and gate have finished.
            validation, qualification = layout['validation'], layout['qualify']
            older, current = matrix[int(returning)], matrix[int(incumbent)]
            validation_gain = sum(int(older[case]) - int(current[case]) for case in validation)
            qualification_gain = sum(int(older[case]) - int(current[case]) for case in qualification)
            total['returnStrictGainAndQualified'] += int(
                validation_gain > 0 and qualification_gain >= plan['minimumQualificationGain'])
        trace.append((incumbent, previous, result.search.prompt, result.prompt, search_hash,
                      [(item.prompt, item.row_id, item.repeat, item.passed) for item in replies]))
        previous, incumbent = (incumbent if promoted else None), result.prompt
    return int(incumbent), total, trace


def prepare():
    parent, phases = source.prepare()
    previous = checked_file('docs/expected-cost-proposal-replay-results-v1.json', REFERENCE)
    checked_file('docs/proposal-gap-audit-results-v1.json', AUDIT)
    if digest(parent) != previous['designSha256']:
        raise ValueError('The previous proposal comparison differs from its seal')
    design = {'protocol': 'cpo-proposal-incumbent-return-v1', 'referenceReportSha256': REFERENCE,
              'gapAuditSha256': AUDIT, 'searchCap': CAP, 'primary': 'return', 'policies': POLICIES,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': ('Replace the second opening after a promotion with the displaced incumbent once. '
                        'Cost and qualify it like any other challenger. The vacant control skips the same slot.')}
    return design, phases, previous['results']


def replay(plan, panels, references, previous):
    original = source.proposal_episode

    def episode(matrix, start, layouts, settings):
        policy = settings['evaluationLookupLimit']
        if policy not in POLICIES:
            return original(matrix, start, layouts, settings)
        return archive_episode(matrix, start, layouts, {**settings, 'evaluationLookupLimit': CAP}, policy=policy)

    with patch.multiple(source, CAPS=CAPS, proposal_episode=episode):
        report = source.measure_phase(plan, panels, references)
    for name, points in report['panels'].items():
        controls = (*source.continuous.GEPA, 'cpo-72', 'cpo-171')
        if any(points[label] != previous[name][label] for label in controls):
            raise ValueError(f'The unchanged budget controls differ from their published receipts for {name}')
    return report


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
    report = {'design': design, 'designSha256': seal, 'results': {
        phase: replay(*inputs, previous[phase]['panels']) for phase, inputs in phases.items()}}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
