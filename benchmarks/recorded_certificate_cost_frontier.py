"""Compare the frozen four-read certificate with GEPA at realized lookup budgets."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import pairwise
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_certificate_allowance_transfer as prior
from benchmarks import witness_validation_cost_frontier as frontier
from cpo._contract import digest


transfer = prior.transfer
adapter = prior.baseline.parent
RECEIPT = 'docs/recorded-certificate-allowance-transfer-results-v1.json'
RECEIPT_SHA256 = 'b7a974a85b28e2278d7107b7c30806715c1e5fa2a5cf8ac906403f8264ff850f'
CANDIDATES = (prior.ARM, transfer.study.FIRST)
MODES = tuple(transfer.CONTROL_NAMES.values())
METRICS = ('holdoutPasses', 'paidLookups')


def prepare():
    parent, _, groups, _ = prior.prepare()
    receipt = prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, parent)
    paths = (Path(__file__), Path(frontier.__file__))
    plan = {**{key: parent[key] for key in ('gepaVersion', 'bootstrapSeed', 'bootstrapDraws', 'searchCap',
                                           'seeds', 'challengers', 'caseCounts')},
            'protocol': 'recorded-certificate-cost-frontier-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'gepaModes': MODES, 'minimumSearchCap': parent['caseCounts'][1], 'policies': CANDIDATES,
            'scope': 'On all four archived target cohorts, retain the frozen CPO deployments and sweep every '
                     'integer GEPA cap from the cost of the initial validation panel to the original cap. '
                     'Use the same expected-cost qualification, roster and held-out cases. Compare at '
                     'realized search plus qualification cost, and reselect the strongest affordable fixed '
                     'GEPA setting or the original start on every paired case resample.'}
    return plan, groups, receipt['results']


def run(arguments, mode, cap):
    return adapter.run_trial(*arguments, cap, mode, adapter.EXPECTED)


def budget_paths(arguments, mode, lowest, highest):
    native = adapter.math.gepa.optimize_by_paid_reads
    quotes = {lowest, highest}

    def capture(incumbent, alternatives, training, validation, observe, spent, *, paid_limit, batched, seed):
        reserve = (2 if batched else 1) * (2 * adapter.math.gepa.legacy.PROBES + len(validation))

        def record_spend():
            count = spent()
            quote = count + reserve
            if lowest <= quote <= highest:
                quotes.add(quote)
            return count

        return native(incumbent, alternatives, training, validation, observe, record_spend,
                      paid_limit=paid_limit, batched=batched, seed=seed)

    # A smaller cap follows this deterministic path until its first unaffordable round.
    with patch.object(adapter.math.gepa, 'optimize_by_paid_reads', capture):
        full = run(arguments, mode, highest)
    paths = {cap: run(arguments, mode, cap) for cap in sorted(quotes - {highest})}
    paths[highest] = full
    return paths


def measure_panel(subject, matrix, plan, reference):
    cells = {str(index): tuple((int(passed), None, False) for passed in vector)
             for index, vector in enumerate(matrix)}
    lowest, highest = plan['minimumSearchCap'], plan['searchCap']
    labels = [f'{mode}/{cap}' for mode in MODES for cap in range(lowest, highest + 1)]
    totals = {label: Counter() for label in labels}
    scores = {label: [0] * reference['holdoutCases'] for label in labels}
    for mode in MODES:
        full_total, full_traces = Counter(), []
        for seed in plan['seeds']:
            start, roster, cohorts = transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
            paths = budget_paths((cells, start, roster, cohorts, seed), mode, lowest, highest)
            full_point, full_trace, _ = paths[highest]
            full_total.update(full_point)
            full_traces.append(full_trace)
            for lower, upper in pairwise((*paths, highest + 1)):
                point, _, grades = paths[lower]
                if (point['searchLookups'] > lower or point['qualificationLookups'] > 2 * len(cohorts[2])
                        or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
                    raise ValueError('A swept search path exceeded its paid allowance')
                for cap in range(lower, upper):
                    label = f'{mode}/{cap}'
                    totals[label].update({key: point[key] for key in METRICS})
                    scores[label] = [a + b for a, b in zip(scores[label], grades, strict=True)]
        if {**full_total, 'traceSha256': digest(full_traces)} != reference['totals'][mode]:
            raise ValueError('GEPA at the original cap must reproduce the published panel and trace')
    return totals, scores


def measure_cohort(panels, plan, reference):
    frozen = (*CANDIDATES, frontier.RETAIN)
    totals = {label: {key: reference['totals'][label][key] for key in METRICS} for label in frozen}
    by_subject = {subject: {label: rows[label] for label in (*frozen, *MODES)}
                  for subject, rows in reference['caseVectorsBySubject'].items()}
    for _, subject, model, matrix in panels:
        points, scores = measure_panel(subject, matrix, plan, reference['panels'][f'{subject}/{model}'])
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            rows = by_subject[subject]
            old = rows.get(label, [0] * len(scores[label]))
            rows[label] = [a + b for a, b in zip(old, scores[label], strict=True)]
    for rows in by_subject.values():
        for mode in MODES:
            if rows.pop(mode) != rows[f"{mode}/{plan['searchCap']}"]:
                raise ValueError('The original-cap GEPA held-out case vector changed')
    if any(sum(sum(rows[label]) for rows in by_subject.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('Every swept score must reproduce its paired case totals')
    settings = tuple(label for label in totals if label not in frozen)
    comparisons = frontier.compare(totals, by_subject, policies=CANDIDATES,
                                   draws=plan['bootstrapDraws'], seed=plan['bootstrapSeed'],
                                   groups={'either-mode': settings})
    return {'totals': totals, 'comparisons': {arm: rows['either-mode'] for arm, rows in comparisons.items()}}


def execute(plan, groups, reference):
    results = {}
    for name, panels in groups.items():
        results[name] = {cohort: measure_cohort([panel for panel in panels if panel[0] == cohort], plan, archived)
                         for cohort, archived in reference[name].items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = execute(plan, groups, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
