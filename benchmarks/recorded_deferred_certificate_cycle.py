"""Verify that deferred reserved probes preserve archived decisions and costs."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import recorded_certificate_budget_route as route
from benchmarks import recorded_certificate_routing_gepa_transfer as transfer
from cpo import Observation, Row
from cpo._contract import digest
from cpo.deferred_certificate_cycle import run_deferred_certificate_cycle
from cpo.threshold_prechecked_cycle import run_threshold_prechecked_cycle


frontier = route.frontier
RETAIN = route.RETAIN
NATIVE_ARCHIVES = {
    'docs/threshold-precheck-gepa-frontier-results-v1.json':
        '2f5c498945d4ef5dbe8b4841047449d426769a59b1ede6d07826cd9ca1f58921',
    'docs/recorded-certificate-routing-gepa-transfer-results-v1.json':
        '3f21b7d5ca9725ca36501b12f4b49a68d003fd611893ef121d6ebf0738cdfb98',
}


def prepare():
    parent, groups, _, _ = route.prepare()
    receipt = frontier.cost.prior.baseline.read_reference(transfer.RECEIPT, transfer.RECEIPT_SHA256, parent)
    native = {}
    for name, expected in NATIVE_ARCHIVES.items():
        raw = (route.ROOT / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError('Use the sealed native comparison receipts')
        native.update(json.loads(raw)['results'])
    paths = (Path(__file__), Path(route.__file__), Path(frontier.__file__),
             Path(route.reserved.__file__), Path(route.threshold.__file__),
             route.ROOT / 'cpo/deferred_certificate_cycle.py', route.ROOT / 'cpo/challenger.py')
    complete_roster_cap = 2 * parent['caseCounts'][1] - 1 + parent['challengers']
    plan = {**parent, 'protocol': 'recorded-deferred-certificate-cycle-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': transfer.RECEIPT_SHA256,
            'nativeReceiptSha256': NATIVE_ARCHIVES,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'screenCaps': (parent['screenCap'], complete_roster_cap),
            'scope': 'Defer the reserved shared probes while preserving exact nominee, deployment, '
                     'qualification callback order, and every non-probe callback. Compare paid lookups '
                     'at the original cap and the first cap that admits the complete challenger roster. '
                     'At the original cap, reprice the frozen native GEPA curves without changing grades.'}
    return plan, groups, receipt['results'], native


def execute_path(cycle, cells, start, roster, cohorts, seed, cap, gain):
    rows = tuple(Row(str(case), 'validation') for case in cohorts[1])
    qualification = tuple(Row(str(case), 'qualification') for case in cohorts[2])
    paid = {}

    def charge(role, prompt, row):
        key = role, prompt, row.id
        if key in paid:
            raise ValueError('The ledger must charge each prompt and case once')
        paid[key] = bool(cells[prompt][int(row.id)])
        return paid[key]

    def qualify(prompt, row, repeat):
        if repeat:
            raise ValueError('The archive pays for each qualification reply once')
        return charge('qualification', prompt, row)

    result = cycle(
        start, roster, rows, qualification,
        lambda prompt, row: Observation(charge('validation', prompt, row), {}),
        metric_limit=cap, qualify=qualify, minimum_gain=gain, seed=seed,
    )
    validation_reads = sum(role == 'validation' for role, _, _ in paid)
    if (validation_reads != result.search.evaluations or validation_reads > cap
            or result.qualification_evaluations != len(paid) - validation_reads
            or result.qualification_evaluations > 2 * len(qualification)):
        raise ValueError('Both separate limits must reconcile with actual dispatch')
    return result, paid


def compare_path(cells, start, roster, cohorts, seed, cap, gain):
    args = cells, start, roster, cohorts, seed, cap, gain
    before, eager = execute_path(run_threshold_prechecked_cycle, *args)
    after, deferred = execute_path(run_deferred_certificate_cycle, *args)
    if (before.search.prompt != after.search.prompt or before.search.finalist != after.search.finalist
            or before.qualification != after.qualification or before.prompt != after.prompt):
        raise ValueError('Deferral must preserve nomination, deployment and the exact qualification receipt')
    if not deferred.items() <= eager.items():
        raise ValueError('Deferral cannot introduce a new paid reply')
    witness = next((str(case) for case in cohorts[1] if not cells[start][case]), None)

    def probe(key):
        role, prompt, row = key
        return role == 'validation' and prompt != start and row == witness

    if any(not probe(key) for key in eager.keys() - deferred.keys()):
        raise ValueError('At these caps only unused challenger probes can be omitted')
    if [key for key in eager if not probe(key)] != [key for key in deferred if not probe(key)]:
        raise ValueError('Deferral must preserve the order of all non-probe callbacks')
    point = {'holdoutPasses': sum(cells[after.prompt][case] for case in cohorts[-1]),
             'eagerLookups': len(eager), 'deferredLookups': len(deferred), 'savedLookups': len(eager) - len(deferred),
             'pathsWithSavings': int(len(eager) > len(deferred)), 'pathsWithReorderedCallbacks': int(
                 [key for key in eager if key in deferred] != list(deferred))}
    def trace(ledger):
        return digest([(*key, passed) for key, passed in ledger.items()])

    return point, trace(eager), trace(deferred)


def native_at_cost(reference, label, budget):
    previous = reference['totals'][label]['paidLookups']
    settings = {name: point for name, point in reference['totals'].items()
                if name.startswith('gepa-') or name == RETAIN}
    affordable = {name: point for name, point in settings.items() if point['paidLookups'] <= budget}
    best = frontier.frontier.highest_scoring(
        {name: point['paidLookups'] for name, point in affordable.items()},
        {name: point['holdoutPasses'] for name, point in affordable.items()}, affordable,
    )
    original = reference['comparison'][label]['either'] if 'comparison' in reference else reference['comparisons'][label]
    return {'bestAffordableControl': {'setting': best, **affordable[best]},
            'removedAffordableSettings': sum(budget < point['paidLookups'] <= previous for point in settings.values()),
            'previousPairedRange95': original['pairedRange95'],
            'subjectHindsightBounds': route.published.hindsight_bounds(reference, budget)}


def measure_cohort(panels, plan, receipt, native):
    totals, fingerprints = {}, {}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        name = f'{subject}/{model}'
        by_panel = fingerprints.setdefault(name, {})
        for cap in plan['screenCaps']:
            for gain, label in frontier.POLICIES.items():
                stats = totals.setdefault(f'cap-{cap}/gain-{gain}', Counter())
                eager, deferred = [], []
                for seed in plan['seeds']:
                    start, roster, roles = frontier.transfer.archive.transfer.schedule(
                        subject, len(matrix[0]), len(matrix), seed, plan,
                    )
                    point, old_path, new_path = compare_path(cells, start, roster, roles, seed, cap, gain)
                    stats.update(point)
                    eager.append(old_path)
                    deferred.append(new_path)
                eager_hash = digest(eager)
                if cap == plan['screenCap'] and eager_hash != receipt['panelPathHashes'][name][label]:
                    raise ValueError('The eager control must reproduce its previously published path')
                by_panel[f'cap-{cap}/gain-{gain}'] = {'eager': eager_hash, 'deferred': digest(deferred)}
    comparisons = {}
    for gain, label in frontier.POLICIES.items():
        key = f"cap-{plan['screenCap']}/gain-{gain}"
        point = totals[key]
        baseline = native['totals'][label]
        if point['holdoutPasses'] != baseline['holdoutPasses'] or point['eagerLookups'] != baseline['paidLookups']:
            raise ValueError('The archive must preserve the prior GEPA comparison budget and score')
        comparisons[key] = native_at_cost(native, label, point['deferredLookups'])
    return {'totals': totals, 'nativeComparisonsAtOriginalCap': comparisons, 'panelPathHashes': fingerprints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, receipt, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    results = {name: measure_cohort(panels, plan, receipt[name], native[name]) for name, panels in groups.items()}
    with args.out.open('x') as destination:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  destination, indent=2, sort_keys=True)
        destination.write('\n')


if __name__ == '__main__':
    main()
