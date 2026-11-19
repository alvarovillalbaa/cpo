"""Compare CPO with official GEPA across a fixed ladder of paid search ceilings."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import archive_complementarity_transfer as cpo
from benchmarks import gepa_paid_cap_transfer as gepa
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
CPO_REPORT_SHA = 'f18c5d115fb4e6c12da907ef1f0a81dd19fbca95e50f45e8f98da8264a14fb6c'
CAPS = (28, 36, 40, 44, 48, 52, 60, 68)
CPO_CAPS = (28, 36, 40, 44, 52)
METHODS = (gepa.CPO, *gepa.METHODS)


def prepare():
    phases = {}
    inputs = {}
    for phase in gepa.reference.transfer.SOURCES:
        cpo_plan, original, data, previous_gepa, _ = cpo.prepare(phase)
        previous_cpo = cpo.checked_report('archive-complementarity-transfer-results-v1.json', CPO_REPORT_SHA, phase)
        if digest(cpo_plan) != previous_cpo['planSha256']:
            raise ValueError('The archive baseline seal differs')
        if min(CAPS) < cpo_plan['validationRows'] + original['qualificationRowsPerCycle']:
            raise ValueError('Every cap must fund the initial incumbent after the archive check')
        phases[phase] = {'planSha256': digest(cpo_plan), 'validationRows': cpo_plan['validationRows']}
        inputs[phase] = (original, data, previous_cpo['panels'], previous_gepa)
    plan = {
        'protocol': 'cpo-paid-budget-frontier-v1', 'parentPhases': phases,
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'gepaVersion': cpo_plan['gepaVersion'], 'gepaCaps': list(CAPS), 'cpoCaps': list(CPO_CAPS),
        'referenceCpoCap': 52, 'archiveReportSha256': CPO_REPORT_SHA,
        'gepaReportSha256': cpo.PAID_CAP_SHA256, 'methods': list(METHODS),
        'scope': 'Fixed proposal rosters and independent qualification with episode-local evidence reuse.',
        'oracle': 'At the reference CPO paid cost, allow hindsight to choose a GEPA cap and method per subject.',
    }
    return plan, inputs


def measure(matrix, held, original, validation_rows, method, cap):
    settings = {'validationRows': validation_rows, 'searchCap': cap}
    totals, journals = Counter(), []
    for seed in original['seeds']:
        if method == gepa.CPO:
            costs, journal = cpo.episode(matrix, held, seed, original, settings, 'recency')
        else:
            _, costs, peak, journal = gepa.reinvest_episode(
                matrix, held, seed, original, settings, batched=method == gepa.METHODS[1])
            if peak > cap:
                raise ValueError('A GEPA trajectory exceeded the paid ceiling')
        totals.update(costs)
        journals.append(journal)
    return {'holdoutPasses': totals['holdoutPasses'], 'paidLookups': totals['searchPaid'] + totals['qualificationPaid'],
            'traceSha256': digest(journals)}


def check_reference(method, point, prior_cpo, prior_gepa):
    if method == gepa.CPO:
        expected = prior_cpo['policies']['recency']
        trace = expected['callbackTraceSha256']
    else:
        expected = prior_gepa['reinvested'][method]
        trace = expected['traceSha256']
    if point != {'holdoutPasses': expected['holdoutPasses'], 'paidLookups': expected['paidLookups'],
                 'traceSha256': trace}:
        raise ValueError('The 52-cap point differs from the published decision and lookup trace')


def measure_panel(panel, original, validation_rows, previous_cpo, previous_gepa):
    subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
    name = f'{subject}/{model}'
    held = original['holdoutCaseIDs'][subject]
    points = {}
    for method in METHODS:
        caps = CPO_CAPS if method == gepa.CPO else CAPS
        measured = {str(cap): measure(matrix, held, original, validation_rows, method, cap) for cap in caps}
        check_reference(method, measured['52'], previous_cpo[name], previous_gepa[name])
        points[method] = measured
    return name, points


def aggregate(panels):
    totals = {}
    for points in panels.values():
        for method, caps in points.items():
            for cap, row in caps.items():
                totals.setdefault(method, {}).setdefault(cap, Counter()).update(
                    holdoutPasses=row['holdoutPasses'], paidLookups=row['paidLookups'])
    return totals


def best_fixed_gepa(totals, budget):
    feasible = [
        {'method': method, 'cap': int(cap), **row}
        for method in gepa.METHODS for cap, row in totals[method].items() if row['paidLookups'] <= budget
    ]
    return max(feasible, key=lambda row: (row['holdoutPasses'], -row['paidLookups']), default=None)


def best_subject_allocation(subjects, budget):
    """Exact cost-constrained hindsight selection over complete, paired model panels."""
    frontier = {0: (0, ())}
    for subject, choices in sorted(subjects.items()):
        next_points = {}
        for cost, (passes, allocation) in frontier.items():
            for row in choices:
                new_cost = cost + row['paidLookups']
                new_score = passes + row['holdoutPasses']
                if new_cost <= budget and new_score > next_points.get(new_cost, (-1, ()))[0]:
                    next_points[new_cost] = (new_score, (*allocation, (subject, row['method'], row['cap'])))
        frontier, best = {}, -1
        for cost, point in sorted(next_points.items()):
            if point[0] > best:
                frontier[cost] = point
                best = point[0]
        if not frontier:
            return None
    cost, (passes, allocation) = max(frontier.items(), key=lambda row: row[1][0])
    return {'holdoutPasses': passes, 'paidLookups': cost, 'allocation': [
        {'subject': subject, 'method': method, 'cap': cap} for subject, method, cap in allocation
    ]}


def summarize(panels):
    totals = aggregate(panels)
    by_subject = {}
    for name, points in panels.items():
        by_subject.setdefault(name.split('/')[0], {})[name] = points
    subject_choices = {
        subject: [{'method': method, 'cap': int(cap), **row}
                  for method, caps in aggregate(group).items() if method in gepa.METHODS
                  for cap, row in caps.items()]
        for subject, group in by_subject.items()
    }
    fixed = {}
    oracle = {}
    for cap, row in totals[gepa.CPO].items():
        budget = row['paidLookups']
        fixed[cap] = best_fixed_gepa(totals, budget)
        oracle[cap] = best_subject_allocation(subject_choices, budget)
    return {'totals': totals, 'bestFixedGepaAtCpoCost': fixed, 'subjectGepaOracleAtCpoCost': oracle}


def replay(plan, inputs):
    panels, cohorts = {}, {}
    for phase, (original, data, cpo_baseline, gepa_baseline) in inputs.items():
        rows = plan['parentPhases'][phase]['validationRows']
        phase_panels = dict(measure_panel(panel, original, rows, cpo_baseline, gepa_baseline) for panel in data)
        if panels.keys() & phase_panels.keys():
            raise ValueError('Transfer panels must remain disjoint')
        panels.update(phase_panels)
        cohorts[phase] = summarize(phase_panels)
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels,
            'cohorts': cohorts, 'combined': summarize(panels)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
