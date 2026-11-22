"""Price same-case reply ordering for the exact deferred qualification proof."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import deferred_certificate_no_regression as reference
from cpo import deferred_certificate_cycle as ordinary
from cpo import paired_order_certificate_cycle as ordered
from cpo._contract import digest


cycle, frontier = reference.cycle, reference.frontier


def prepare():
    parent, groups, receipts, controls, ceilings, native = reference.prepare()
    paths = (Path(__file__), Path(ordinary.__file__), Path(ordered.__file__),
             reference.ROOT / 'cpo/expected_qualification.py')
    plan = {**parent, 'protocol': 'deferred-certificate-paired-order-v1',
            'parentPlanSha256': digest(parent),
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'scope': 'Keep fixed one- and two-gain qualification thresholds, paid precheck, search, '
                     'and exact decisions. For the next qualification reply, shrink the estimated pass '
                     'probability halfway toward the already-observed partner grade, when available. '
                     'Use the original remaining-cost calculation from the resulting state. Compare '
                     'paid order, costs and exact qualification decisions on the full-roster archive.'}
    return plan, groups, receipts, controls, ceilings, native


def measure_cohort(panels, plan, receipt, controls, ceilings, native):
    totals = {label: Counter() for label in controls.values()}
    fingerprints = {}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        paths = {label: [] for label in controls.values()}
        before = {label: [] for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, plan['fullRosterCap'], gain
                old, old_paid = cycle.execute_path(ordinary.run_deferred_certificate_cycle, *args)
                new, paid = cycle.execute_path(ordered.run_paired_order_certificate_cycle, *args)
                if old.search != new.search or old.prompt != new.prompt or old.promoted != new.promoted:
                    raise ValueError('Reply order must preserve nomination, deployment, and search spend')
                if ([(key, grade) for key, grade in old_paid.items() if key[0] == 'validation']
                        != [(key, grade) for key, grade in paid.items() if key[0] == 'validation']):
                    raise ValueError('Every validation callback must match')
                original, old_grades, original_path = reference.point(cells, roles[-1], old, old_paid)
                actual, grades, path = reference.point(cells, roles[-1], new, paid)
                if grades != old_grades:
                    raise ValueError('The paired score must reproduce')
                saved = original['paidLookups'] - actual['paidLookups']
                totals[label].update(holdoutPasses=actual['holdoutPasses'], originalLookups=original['paidLookups'],
                                     pairedLookups=actual['paidLookups'], cheaperPaths=int(saved > 0),
                                     dearerPaths=int(saved < 0))
                before[label].append(original_path)
                paths[label].append(path)
        name = f'{subject}/{model}'
        fingerprints[name] = {label: digest(path) for label, path in paths.items()}
        if any(digest(path) != receipt['panelPathHashes'][name][label]['deferred'] for label, path in before.items()):
            raise ValueError('The original one- and two-gain callbacks must exactly reproduce')
    for label, row in totals.items():
        expected = ceilings['comparisons'][label]['cpo']
        if (row['holdoutPasses'] != expected['holdoutPasses'] or row['originalLookups'] != expected['paidLookups']):
            raise ValueError('The original fixed-margin scores and costs must reproduce')
    return {'totals': totals, 'panelPathHashes': fingerprints,
            'nativeSubjectHindsightBounds': {
                label: reference.hindsight_bounds(native, ceilings['comparisons'], row['pairedLookups'])
                for label, row in totals.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, receipts, controls, ceilings, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    results = {name: measure_cohort(panels, plan, receipts[name], controls, ceilings[name], native[name])
               for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
