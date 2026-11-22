"""Fund exact two-sided validation from a shared incumbent prefix."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import deferred_certificate_probe_allocation as previous
from cpo._contract import digest
from cpo import two_sided_certificate_cycle as cycle


paired = previous.paired
REPORT = 'docs/deferred-certificate-probe-allocation-results-v1.json'
REPORT_SHA256 = '476e3eb08541a1dd4a078794d5aab90fa5a8a844d7d5124fb283382fdc9f44e1'
ROW, EXPECTED = 'paired-row-order', 'paired-expected-order'
POLICIES = ROW, EXPECTED


def prepare():
    parent, panels, controls, _, native = previous.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    earlier = read(REPORT, REPORT_SHA256, parent)['results']
    sources = (Path(__file__), Path(cycle.__file__), paired.reference.ROOT / 'cpo/expected_qualification.py')
    plan = {**parent, 'protocol': 'deferred-two-sided-certificate-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REPORT_SHA256,
            'sourceSha256': {p.name: sha256(p.read_bytes()).hexdigest() for p in sources},
            'methods': POLICIES,
            'scope': 'Read the incumbent through its first validation miss. Reserve one shared probe '
                     'for each unvisited challenger. Use the remaining flexible balance to certify '
                     'each positive probe from known challenger passes and incumbent misses, including '
                     'incumbent replies accumulated by earlier certificates. Use paired row order or '
                     'expected-cost order with same-case evidence. Revisit shared-probe misses after '
                     'positive probes. Keep the exact disjoint qualification rule and roster.'}
    return plan, panels, controls, earlier, native


def run_trial(policy, args):
    runner = cycle.run_two_sided_certificate_cycle
    if policy == ROW:
        runner = partial(cycle._run, screen=partial(cycle._screen, expected=False))
    return paired.cycle.execute_path(runner, *args)


def measure(panels, plan, controls, earlier, native):
    stats = {label: {policy: Counter() for policy in POLICIES} for label in controls.values()}
    audits = {label: {policy: Counter() for policy in POLICIES} for label in controls.values()}
    paths = {}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        panel = f'{subject}/{model}'
        traces = {label: {policy: [] for policy in (previous.BASE, *POLICIES)} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, plan['fullRosterCap'], gain
                shared, old = paired.cycle.execute_path(paired.ordered.run_paired_order_certificate_cycle, *args)
                anchor, _, trace = paired.reference.point(cells, roles[-1], shared, old)
                traces[label][previous.BASE].append(trace)
                for policy in POLICIES:
                    result, paid = run_trial(policy, args)
                    previous.check_deployment(cells, start, roles, result, gain)
                    incumbent_reads = sum(role == 'validation' and prompt == start for role, prompt, _ in paid)
                    certified = result.search.finalist is not None
                    audits[label][policy].update(
                        incumbentLookups=incumbent_reads, certified=int(certified),
                        partialIncumbentCertificates=int(certified and incumbent_reads < len(roles[1])),
                    )
                    point, _, trace = paired.reference.point(cells, roles[-1], result, paid)
                    stats[label][policy].update(
                        **point, searchLookups=result.search.evaluations,
                        changedNominee=int(result.search.prompt != shared.search.prompt),
                        changedDeployment=int(result.prompt != shared.prompt),
                        holdoutDifference=point['holdoutPasses'] - anchor['holdoutPasses'],
                        lookupDifference=point['paidLookups'] - anchor['paidLookups'],
                        incumbentLookupDifference=incumbent_reads - sum(
                            role == 'validation' and prompt == start for role, prompt, _ in old),
                    )
                    traces[label][policy].append(trace)
        paths[panel] = {label: {policy: digest(trace) for policy, trace in methods.items()}
                        for label, methods in traces.items()}
        if any(paths[panel][label][previous.BASE] != earlier['panelPathHashes'][panel][label][previous.BASE]
               for label in controls.values()):
            raise ValueError('Every baseline callback trace must reproduce')
    comparisons = tuple((row['cpo']['paidLookups'], row['expandedSubjectCeiling'])
                        for row in native['comparisons'].values())
    bounds = {}
    for label, points in stats.items():
        bounds[label] = {}
        for policy, point in points.items():
            if any(point[key] - point[delta] != earlier['totals'][label][previous.BASE][key]
                   for key, delta in (('holdoutPasses', 'holdoutDifference'), ('paidLookups', 'lookupDifference'))):
                raise ValueError('Scores and paired cost changes must reconcile to the shared-probe baseline')
            budget = point['paidLookups']
            bounds[label][policy] = {
                'lowerPasses': max((row['holdoutPasses'] for _, row in comparisons if row['paidLookups'] <= budget),
                                   default=None),
                'upperPasses': min((row['holdoutPasses'] for limit, row in comparisons if limit >= budget),
                                   default=None),
            }
    return {'totals': stats, 'proofAudit': audits, 'nativeGepaBounds': bounds, 'panelPathHashes': paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, controls, earlier, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: measure(cohort, plan, controls, earlier[name], native[name]) for name, cohort in panels.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
