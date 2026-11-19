"""Compare nested validation panels with the original, disjoint qualification schedule."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_archive_cycles as archive, prompteval_continuous as continuous
from benchmarks import prompteval_round_reserve as attribution
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '5129a9264e1c756de583b2d1ddf030827f2d6530519eea9213a9973e352f217f'
DESIGNS = {'full': (24, 88), 'half-fixed-budget': (12, 88), 'half-scaled-budget': (12, 52),
           'third-scaled-budget': (8, 40)}


def narrow_schedule(initial, layouts, rows):
    if not layouts or not 1 <= rows <= min(len(layout['validation']) for layout in layouts):
        raise ValueError('Validation prefix must fit every scheduled panel')
    return initial, [{**layout, 'validation': layout['validation'][:rows]} for layout in layouts]


def episode(matrix, held, seed, original, rows, cap):
    upstream = continuous.schedule

    def schedule(*args):
        return narrow_schedule(*upstream(*args), rows)

    with patch.object(continuous, 'schedule', schedule):
        return attribution.attributed_episode(matrix, held, seed, {**original, 'evaluationLookupLimit': cap}, 'adaptive')


def prepare(phase):
    parent, original, source, _ = attribution.prepare(phase, 88)
    full = (ROOT / 'docs/prompteval-round-reserve-results-v1.json').read_bytes()
    if sha256(full).hexdigest() != SOURCE_SHA256:
        raise ValueError('Published role attribution differs from the verified source')
    archived = json.loads(full, object_pairs_hook=unique_object)
    previous = next(report for report in archived['runs'] if report['phase'] == phase and report['searchCap'] == 88)
    if digest(parent) != previous['planSha256'] or original['validationRows'] != DESIGNS['full'][0]:
        raise ValueError('Published full validation plan differs from the verified source')
    for rows, cap in DESIGNS.values():
        # Full incumbent validation, one batched round, and the archive challenger reserve.
        if cap < rows + 2 * (2 * original['probeSize'] + rows) + original['qualificationRowsPerCycle']:
            raise ValueError('Each design must fund a batched round after the archive probe')
    _, _, full_cap, _ = archive.prepare(phase, 171)
    plan = {'protocol': 'cpo-prompteval-validation-size-v1', 'phase': phase,
            'parentPlanSha256': previous['planSha256'], 'parentReportSha256': previous['reportSha256'],
            'publishedRoleSummarySha256': SOURCE_SHA256, 'gepaVersion': original['gepaVersion'],
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'designs': DESIGNS,
            'panelSampling': 'A prefix of the seeded 24 validation cases. Training, proposal order, qualification, and holdout are fixed.',
            'scaledBudget': 'Fund incumbent validation and one batched round after up to eight archive challenger lookups.'}
    return plan, original, source, previous['panels'], full_cap['panels']


def compare(left, right):
    passes = left['holdoutPasses'] - right['holdoutPasses']
    cost_l = left['searchLookups'] + left['qualificationLookups']
    cost_r = right['searchLookups'] + right['qualificationLookups']
    return {'deltaPasses': passes, 'deltaLookups': cost_l - cost_r,
            'qualified': passes >= 0 and cost_l <= cost_r and (passes > 0 or 10 * cost_l <= 9 * cost_r)}


def replay(plan, original, source, published, full_cap):
    panels = {}
    fields = ('train', 'validation', 'qualification')
    candidates = ('incumbent', 'completeChallenger', 'partialChallenger')
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        results = {design: attribution.summarize([episode(matrix, held, seed, original, rows, cap)
                                                  for seed in original['seeds']])
                   for design, (rows, cap) in DESIGNS.items()}
        base = results['full']
        for method, total in base['totals'].items():
            observed = [total['holdoutPasses'], *(base['callsByRole'][method][key] for key in fields),
                        *(base['validationByCandidate'][method][key] for key in candidates)]
            if observed != published[name]['adaptive']['totals'][method]:
                raise ValueError('The full-panel baseline differs from the published role counts')
        for result in results.values():
            current = result['totals']['cpo-cycle.runner-up']
            result['fullPanelComparison'] = compare(current, base['totals']['cpo-cycle.runner-up'])
            result['fullBudgetGepaComparisons'] = {arm: compare(current, full_cap[name]['totals'][arm])
                                                    for arm in continuous.GEPA}
        panels[name] = results
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=archive.PHASES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, original, source, published, full_cap = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, original, source, published, full_cap)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
