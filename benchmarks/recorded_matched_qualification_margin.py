"""Compare CPO with native GEPA under identical stronger qualification."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import pairwise
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_qualification_margin as prior
from cpo._contract import digest


cost, frontier = prior.cost, prior.frontier
CPO = prior.CANDIDATE
RECEIPT = 'docs/recorded-qualification-margin-results-v1.json'
RECEIPT_SHA256 = 'cff0abd264ef74d911c329334c3cd4b9ba5a8dc0f3f8c2c77402c849d7d451ce'


def prepare():
    source, groups, native, references = prior.prepare()
    receipt = cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, source)
    paths = (Path(__file__), Path(prior.__file__), Path(cost.__file__))
    plan = {**source, 'protocol': 'recorded-matched-qualification-margin-v1',
            'parentPlanSha256': digest(source), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'nativeQualificationGains': (1, 2),
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the strongest '
                    'affordable native GEPA setting with either qualification gain or retained starts',
            'scope': 'Keep each original GEPA search path and run the one- and two-gain qualification '
                     'rules with paid incumbent prefix credit. Retain the frozen two-gain CPO result. '
                     'Sweep both GEPA modes across all original caps. Compare the equally qualified '
                     'controls and the strongest affordable control across both qualification rules. '
                     'Also report the subject-specific GEPA hindsight ceiling under the same cohort budget.'}
    return plan, groups, native, references, receipt['results']


def native_paths(arguments, mode, low, high):
    baseline = cost.budget_paths(arguments, mode, low, high)
    with patch.object(cost.adapter, 'qualify_with_prefix', prior.minimum_two):
        stronger = cost.budget_paths(arguments, mode, low, high)
    if baseline.keys() != stronger.keys():
        raise ValueError('The proof rule cannot change any native search reservation boundary')
    cells, start, _, (_, _, qualification, _), _ = arguments
    for cap, (point, trace, _) in stronger.items():
        old_point, old_trace, _ = baseline[cap]
        if trace[:3] != old_trace[:3] or point['searchLookups'] != old_point['searchLookups']:
            raise ValueError('Changing qualification must keep the native search and nominee')
        nominee = trace[2]
        gain = sum(cells[nominee][case][0] - cells[start][case][0] for case in qualification)
        if (trace[3] != (nominee if gain >= 2 else start)
                or point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(qualification)
                or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
            raise ValueError('The GEPA nominee needs the same funded, exact two-gain proof')
    return baseline, stronger


def measure_native(subject, matrix, plan, anchor):
    cells = {str(index): tuple((int(passed), None, False) for passed in vector) for index, vector in enumerate(matrix)}
    totals, vectors = {}, {}
    paths_checked = 0
    low, high = plan['minimumSearchCap'], plan['searchCap']
    for mode in cost.MODES:
        old_totals, old_traces = Counter(), []
        for seed in plan['seeds']:
            start, roster, cohorts = prior.transfer.fixed.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan)
            baseline, stronger = native_paths((cells, start, roster, cohorts, seed), mode, low, high)
            old_point, trace, _ = baseline[high]
            old_totals.update(old_point)
            old_traces.append(trace)
            paths_checked += len(baseline)
            for qualification_gain, paths in ((1, baseline), (2, stronger)):
                for lower, upper in pairwise((*paths, high + 1)):
                    point, _, grades = paths[lower]
                    measured = {metric: point[metric] for metric in cost.METRICS}
                    for cap in range(lower, upper):
                        label = f'{mode}/{cap}/gain-{qualification_gain}'
                        totals.setdefault(label, Counter()).update(measured)
                        prior.transfer.fixed.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)
        if {**old_totals, 'traceSha256': digest(old_traces)} != anchor[mode]:
            raise ValueError('Unmodified original-cap GEPA must match the archived native trace')
    return totals, vectors, paths_checked


def replay_cohort(cohort, panels, plan, native, reference, archived):
    totals, subjects, by_subject, details = {}, {}, {}, {}
    search_paths = 0
    for subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        point, vector, counts, trace = prior.measure_margin(subject, matrix, plan)
        if {'events': counts, 'traceSha256': trace} != archived['panels'][panel]:
            raise ValueError('The CPO two-gain decision must exactly reproduce')
        anchor = (reference['panels'][panel]['nativeAtOriginalCap'] if cohort == prior.TRANSFER
                  else native['panelsAtOriginalCap'][panel])
        gepa, native_vectors, checked = measure_native(subject, matrix, plan, anchor)
        search_paths += checked
        cells = {str(index): tuple(int(grade) for grade in row) for index, row in enumerate(matrix)}
        retain = [0] * len(vector)
        for seed in plan['seeds']:
            start, _, cohorts = prior.transfer.fixed.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan)
            prior.transfer.fixed.fitted.prior.add_vector(retain, (cells[start][case] for case in cohorts[-1]))
        values = {**native_vectors, CPO: vector, frontier.RETAIN: retain}
        scores = subjects.setdefault(subject, {})
        priced = by_subject.setdefault(subject, {})
        for label, metrics in {**gepa, CPO: point,
                               frontier.RETAIN: {'holdoutPasses': sum(retain), 'paidLookups': 0}}.items():
            totals.setdefault(label, Counter()).update(metrics)
            priced.setdefault(label, Counter()).update(metrics)
            grades = values[label]
            prior.transfer.fixed.fitted.prior.add_vector(scores.setdefault(label, [0] * len(grades)), grades)
        details[panel] = {'retainedPasses': sum(retain), 'nativePathsChecked': checked}
    if any(totals[label] != archived['totals'][label] for label in (CPO, frontier.RETAIN)):
        raise ValueError('The CPO and retained start scores must match the prior qualification replay')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('The native and CPO scores must reconcile with paired cases')
    before = tuple(label for label in totals if label.endswith('/gain-1'))
    matched = tuple(label for label in totals if label.endswith('/gain-2'))
    comparisons = frontier.compare(totals, subjects, policies=(CPO,), draws=plan['bootstrapDraws'],
                                   seed=plan['bootstrapSeed'],
                                   groups={'gain-1': before, 'gain-2': matched, 'either': (*before, *matched)})[CPO]
    prior_comparison = dict(comparisons['gain-1'])
    for key in ('bestWithinCost', 'cheapestMatching'):
        label = prior_comparison[key]
        if label is not None and label != frontier.RETAIN:
            prior_comparison[key] = label.removesuffix('/gain-1')
    prior_comparison['resampledChoices'] = {label.removesuffix('/gain-1'): value
                                           for label, value in prior_comparison['resampledChoices'].items()}
    if prior_comparison != archived['comparison']['native-gepa']:
        raise ValueError('The original complete matched-budget GEPA comparison must reproduce')
    hindsight = prior.transfer.fixed.fitted.prior.by_subject_ceiling(
        by_subject, (*before, *matched), {CPO: totals[CPO]['paidLookups']})[CPO]
    joint = comparisons['either']
    return {'totals': totals, 'comparison': comparisons, 'panels': details,
            'nativeSearchPathsChecked': search_paths, 'subjectTunedGepaHindsight': hindsight,
            'passedArchiveGate': joint['holdoutPassDifference'] > 0 and joint['pairedRange95'][0] >= 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, native, references, archived = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {cohort: replay_cohort(cohort, panels, plan, native, references[cohort], archived[cohort])
               for cohort, panels in groups.items()}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}, output,
                  indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
