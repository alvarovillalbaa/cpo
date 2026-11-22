"""Compare full-roster deferred certificates with affordable native GEPA."""

import argparse
from bisect import bisect_right
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_deferred_certificate_cycle as deferred
from cpo._contract import digest


frontier = deferred.frontier
native_cost = frontier.cost
add_vector = frontier.transfer.fitted.prior.add_vector
RECEIPT = 'docs/deferred-certificate-cycle-results-v1.json'
RECEIPT_SHA256 = '2bf7107a2e761aa55c4c9d5055aaade0012e3e3bf956317f63c8396d5963369f'


def prepare():
    parent, groups, _, native = deferred.prepare()
    receipt = native_cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, parent)
    cap = parent['screenCaps'][-1]
    policies = {gain: f'cap-{cap}/gain-{gain}' for gain in frontier.POLICIES}
    controls = {}
    for cohort, report in receipt['results'].items():
        maximum = max(report['totals'][label]['deferredLookups'] for label in policies.values())
        controls[cohort] = {label: point for label, point in native[cohort]['totals'].items()
                            if label.startswith('gepa-') and point['paidLookups'] <= maximum}
    paths = (Path(__file__), Path(deferred.__file__), Path(frontier.__file__), Path(deferred.transfer.__file__))
    plan = {**parent, 'protocol': 'recorded-deferred-certificate-gepa-frontier-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'fullRosterCap': cap, 'controlsSha256': digest(controls),
            'scope': 'Compare deferred CPO at the frozen full-roster cap with every native GEPA '
                     'setting affordable under either CPO margin, using sealed full-cohort costs. '
                     'Verify the paid CPO callback paths and all eligible native points. '
                     'Reselect the best affordable common GEPA setting or retained starts in every draw.'}
    return plan, groups, receipt['results'], policies, controls


def native_points(arguments, labels, low):
    by_mode = {}
    for label in labels:
        mode, cap, rule = label.split('/')
        by_mode.setdefault(mode, []).append((int(cap), rule, label))
    for mode, settings in by_mode.items():
        high = max(cap for cap, _, _ in settings)
        one, two = frontier.matched.native_paths(arguments, mode, low, high)
        with patch.object(native_cost, 'run', frontier.gepa_threshold):
            threshold = native_cost.budget_paths(arguments, mode, low, high)
        paths = {'gain-1': one, 'gain-2': two, frontier.THRESHOLD: threshold}
        boundaries = {rule: tuple(replayed) for rule, replayed in paths.items()}
        for cap, rule, label in settings:
            stops = boundaries[rule]
            point, _, grades = paths[rule][stops[bisect_right(stops, cap) - 1]]
            yield label, {metric: point[metric] for metric in native_cost.METRICS}, grades


def measure_cohort(panels, plan, receipt, policies, controls):
    totals, subjects = {}, {}
    cap = plan['fullRosterCap']
    for subject, model, matrix in panels:
        cells = {str(i): tuple(map(int, row)) for i, row in enumerate(matrix)}
        native_cells = {prompt: tuple((grade, None, False) for grade in row) for prompt, row in cells.items()}
        scores = subjects.setdefault(subject, {})

        def tally(label, point, grades):
            totals.setdefault(label, Counter()).update(point)
            add_vector(scores.setdefault(label, [0] * len(grades)), grades)

        paths = {label: [] for label in policies.values()}
        for seed in plan['seeds']:
            start, roster, cohorts = frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            kept = tuple(cells[start][case] for case in cohorts[-1])
            tally(deferred.RETAIN, {'holdoutPasses': sum(kept), 'paidLookups': 0}, kept)
            for gain, label in policies.items():
                result, paid = deferred.execute_path(deferred.run_deferred_certificate_cycle, cells, start, roster,
                                                     cohorts, seed, cap, gain)
                grades = tuple(cells[result.prompt][case] for case in cohorts[-1])
                tally(label, {'holdoutPasses': sum(grades), 'paidLookups': len(paid)}, grades)
                paths[label].append(digest([(*key, passed) for key, passed in paid.items()]))
            for label, point, grades in native_points((native_cells, start, roster, cohorts, seed),
                                                     controls, plan['minimumSearchCap']):
                tally(label, point, grades)
        anchor = receipt['panelPathHashes'][f'{subject}/{model}']
        if any(digest(path) != anchor[label]['deferred'] for label, path in paths.items()):
            raise ValueError('Both full-roster CPO callback paths must reproduce for every model panel')
    if any(totals[label] != point for label, point in controls.items()):
        raise ValueError('All affordable native GEPA curves must reproduce their sealed scores and costs')
    for label in policies.values():
        point = receipt['totals'][label]
        if totals[label] != {'paidLookups': point['deferredLookups'], 'holdoutPasses': point['holdoutPasses']}:
            raise ValueError('Both CPO budgets and held-out grades must reproduce')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('Every native and CPO total needs a paired case vector')
    distinct = deferred.transfer.distinct_controls(controls, totals, subjects)
    paired = frontier.frontier.compare(totals, subjects, policies=tuple(policies.values()),
                                       draws=plan['bootstrapDraws'], seed=plan['bootstrapSeed'],
                                       groups={'matched-cost': distinct})
    comparisons = {label: row['matched-cost'] for label, row in paired.items()}
    gates = {label: row['holdoutPassDifference'] > 0 and row['pairedRange95'][0] >= 0
             for label, row in comparisons.items()}
    return {'totals': totals, 'comparisons': comparisons, 'passedGate': gates,
            'nativeSettings': len(controls), 'distinctNativeSettings': len(distinct),
            'caseVectorsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, receipt, policies, controls = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: measure_cohort(panels, plan, receipt[name], policies, controls[name])
               for name, panels in groups.items()}
    with args.out.open('x') as destination:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  destination, indent=2, sort_keys=True)
        destination.write('\n')


if __name__ == '__main__':
    main()
