"""Require corroboration on two fresh cases for a one-pass promotion."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import expected_cost_proposal_replay as source
from benchmarks.case_difficulty_allocation import checked_file
from cpo import Row
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


REFERENCE = 'a340fc3fc1ea6757a691ad594a54a13f500adf2d22328db65707e48b9c1289e5'
PREVIOUS = '9575d156a43e1366080186118d4d88e1e5ec2b765eb34f838e0e4fca33df0b78'
CAP = 72
EXTRA_ROWS = 2
POLICIES = ('corroborate', 'audit')
CAPS = (CAP, *POLICIES, 171)


def reserve_cases(case_count, held, seed, layouts):
    used = set(held).union(*(layout[key] for layout in layouts for key in ('train', 'validation', 'qualify')))
    unused = sorted(set(range(case_count)) - used)
    rng = Random(f'cpo-proposal-corroboration-v1:{seed}')
    rng.shuffle(unused)
    slots = list(range(len(layouts)))
    rng.shuffle(slots)
    reserves = {}
    for position, slot in enumerate(slots):
        block = unused[position * EXTRA_ROWS:(position + 1) * EXTRA_ROWS]
        if len(block) == EXTRA_ROWS:
            reserves[slot] = block
    return [{**layout, 'corroborate': reserves.get(index, [])} for index, layout in enumerate(layouts)]


def corroborate(matrix, incumbent, result, rows, layout, *, enforce, counters):
    reserved = layout['corroborate']
    counters['cyclesWithReserve'] += int(bool(reserved))
    if not result.promoted or result.qualification.lower_gain >= 2:
        return result.prompt, []
    if not reserved:
        counters['promotionWithoutReserve'] += 1
        return result.prompt, []

    decision = result.qualification
    candidate = result.prompt
    cached = {(item.prompt, item.row_id): item.passed for item in decision.observations}
    added = []

    def read(prompt, row, _repeat):
        key = (prompt, row.id)
        if key not in cached:
            passed = matrix[int(prompt)][int(row.id)] == '1'
            cached[key] = passed
            added.append((prompt, row.id, passed))
        return cached[key]

    if decision.upper_gain >= 2:
        stronger = certify_paired_qualification(incumbent, candidate, rows, read, minimum_gain=2, seed=layout['seed'])
        counters['marginLookups'] += len(added)
        if stronger.status == 'promoted':
            return candidate, added

    gain = sum(read(candidate, row, 0) - read(incumbent, row, 0) for row in
               (Row(str(case), 'task') for case in reserved))
    vetoed = gain < 1
    counters.update(corroborationLookups=2 * len(reserved), onePassPromotions=1,
                    corroborated=int(not vetoed), vetoed=int(enforce and vetoed))
    return (incumbent if enforce and vetoed else candidate), added


def archive_episode(matrix, initial, layouts, plan, *, policy):
    incumbent, total, trace = initial, Counter(), []
    for layout in layouts:
        result, rows, search_hash = source.archive_step(matrix, incumbent, layout, plan)
        selected, added = corroborate(matrix, incumbent, result, rows, layout,
                                      enforce=policy == 'corroborate', counters=total)
        replies = () if result.qualification is None else result.qualification.observations
        total.update(searchLookups=result.search.evaluations, expected=len(replies) + len(added),
                     promotions=int(selected != incumbent), reflections=result.search.reflections,
                     addedLookups=len(added))
        original_path = (incumbent, result.search.prompt, selected, search_hash,
                         [(item.prompt, item.row_id, item.repeat, item.passed) for item in replies])
        trace.append(original_path if policy == 'audit' else (*original_path, result.prompt, added))
        incumbent = selected
    return int(incumbent), total, trace


def prepare():
    parent, phases = source.prepare()
    previous = checked_file('docs/expected-cost-proposal-replay-results-v1.json', REFERENCE)
    checked_file('docs/proposal-incumbent-return-results-v1.json', PREVIOUS)
    if digest(parent) != previous['designSha256']:
        raise ValueError('The previous proposal comparison differs from its seal')
    design = {'protocol': 'cpo-proposal-qualification-corroboration-v1', 'referenceReportSha256': REFERENCE,
              'previousReportSha256': PREVIOUS, 'searchCap': CAP, 'reservedRowsPerCycle': EXTRA_ROWS,
              'primary': 'corroborate', 'policies': POLICIES,
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': ('Keep search and original qualification fixed. For each one-pass promotion, require a gain '
                        'on two cases unused by any other stage in the episode when a full reserve is available. '
                        'The audit control pays for both checks and keeps the original decision.')}
    return design, phases, previous['results']


def replay(plan, panels, references, previous):
    original = source.proposal_episode
    schedule = source.continuous.schedule

    def episode(matrix, start, layouts, settings):
        policy = settings['evaluationLookupLimit']
        if policy not in POLICIES:
            return original(matrix, start, layouts, settings)
        return archive_episode(matrix, start, layouts, {**settings, 'evaluationLookupLimit': CAP}, policy=policy)

    def with_reserve(case_count, template_count, held, seed, settings):
        start, layouts = schedule(case_count, template_count, held, seed, settings)
        return start, reserve_cases(case_count, held, seed, layouts)

    with (patch.multiple(source, CAPS=CAPS, proposal_episode=episode),
          patch.object(source.continuous, 'schedule', with_reserve)):
        report = source.measure_phase(plan, panels, references)
    for name, points in report['panels'].items():
        if any(points[label] != previous[name][label] for label in (*source.continuous.GEPA, 'cpo-72', 'cpo-171')):
            raise ValueError(f'The unchanged controls differ from their published receipts for {name}')
        audit, original = points['cpo-audit'], points['cpo-72']
        if (any(audit[key] != original[key] for key in
                ('traceSha256', 'holdoutPasses', 'searchLookups', 'reflections', 'promotions'))
                or audit['expected'] != original['expected'] + audit['addedLookups']):
            raise ValueError(f'The audit control changed the original deployment or charge for {name}')
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
