"""Sweep the validation-tail CPO caps against the same paid GEPA frontier."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import recorded_validation_tail_language_frontier as prior
from cpo import pool
from cpo._contract import digest


RECEIPT = 'docs/recorded-validation-tail-language-frontier-results-v1.json'
RECEIPT_SHA256 = '70c84e44d1db225532b2485e51a43b5d4121c728e33e5102a635b43c4ba659ae'
RETAIN = prior.frontier.RETAIN


def prepare():
    parent, panels, anchors, _ = prior.prepare()
    receipt = prior.cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, parent)
    cohorts = receipt['language']
    budgets = {}
    for cohort, row in cohorts.items():
        full = row['comparisons'][prior.baseline]
        budgets[cohort] = sorted({
            full['commonCap']['bestWithinCostPoint']['paidLookups'],
            full['subjectTunedHindsight']['paidLookups'],
            *(row['totals'][policy]['paidLookups'] for policy in prior.POLICIES),
        })
    full_pool = (parent['challengers'] + 1) * parent['caseCounts'][1]
    plan = {**parent, 'protocol': 'recorded-validation-tail-matched-caps-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest()
                             for path in map(Path, (__file__, prior.__file__, prior.tail.__file__, pool.__file__))},
            'maximumSweptCpoCap': full_pool, 'realizedCohortBudgets': budgets,
            'scope': 'Directly replay each CPO selector from the minimum validation cap through the full '
                     'pool price. Reproduce the original-cap CPO paths and both GEPA curves. At each '
                     'realized cohort budget from the published comparison, allow both suites the same '
                     'fixed-cap or subject-specific flexibility. Reselect both common settings on each '
                     'paired case draw. All frontier winners are descriptive hindsight choices.'}
    return plan, panels, anchors, cohorts


def cpo_trial(arguments, policy, cap):
    if policy == prior.baseline:
        return prior.reference_runner.prior.run_trial(*arguments, cap, ())[:3]
    return prior.tail.run_trial(*arguments, cap, prior.tail.TAILS[policy])


def cpo_panel(subject, matrix, plan, heldout_size):
    cells = {str(index): tuple((int(passed), None, False) for passed in vector) for index, vector in enumerate(matrix)}
    caps = tuple(range(plan['minimumSearchCap'], plan['maximumSweptCpoCap'] + 1))
    totals, vectors = {}, {}
    traces = {policy: [] for policy in prior.POLICIES}
    for seed in plan['seeds']:
        start, roster, cohorts = prior.reference_runner.language.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        holdout = [cells[start][case][0] for case in cohorts[-1]]
        totals.setdefault(RETAIN, Counter()).update(holdoutPasses=sum(holdout), paidLookups=0)
        prior.add_vector(vectors.setdefault(RETAIN, [0] * heldout_size), holdout)
        for policy in prior.POLICIES:
            original = cpo_trial(arguments, policy, plan['searchCap'])
            traces[policy].append(original[1])
            for cap in caps:
                point, trace, grades = cpo_trial(arguments, policy, cap)
                if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
                        or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
                    raise ValueError('CPO exceeded the funded search or qualification allowance')
                if cap == caps[-1] and (point, trace, grades) != original:
                    raise ValueError('The full-pool cap must reproduce the original episode exactly')
                label = f'{policy}/{cap}'
                totals.setdefault(label, Counter()).update({key: point[key] for key in prior.cost.METRICS})
                prior.add_vector(vectors.setdefault(label, [0] * heldout_size), grades)
    return totals, vectors, {policy: digest(trace) for policy, trace in traces.items()}


def common_frontiers(by_subject, totals, groups, budgets, plan):
    subjects = [by_subject[key] for key in sorted(by_subject)]
    costs = {label: point['paidLookups'] for label, point in totals.items()}
    scores = {label: point['holdoutPasses'] for label, point in totals.items()}
    best = prior.frontier.highest_scoring
    eligible = {}
    for group, labels in groups.items():
        # Only discard settings that have the same score on every individual case.
        cheapest = {}
        for label in sorted((*labels, RETAIN), key=lambda name: (costs[name], name)):
            signature = tuple(tuple(subject[label]) for subject in subjects)
            cheapest.setdefault(signature, label)
        eligible[group] = {budget: tuple(label for label in cheapest.values() if costs[label] <= budget)
                           for budget in budgets}
    options = sorted({label for family in eligible.values() for labels in family.values() for label in labels})
    samples = {budget: [] for budget in budgets}
    rng = Random(plan['bootstrapSeed'])
    for _ in range(plan['bootstrapDraws']):
        drawn = Counter()
        for subject in subjects:
            size = len(subject[RETAIN])
            weights = tuple(Counter(rng.randrange(size) for _ in range(size)).items())
            for label in options:
                vector = subject[label]
                drawn[label] += sum(vector[index] * count for index, count in weights)
        for budget in budgets:
            cpo = best(costs, drawn, eligible['cpo'][budget])
            gepa = best(costs, drawn, eligible['gepa'][budget])
            samples[budget].append(drawn[cpo] - drawn[gepa])
    results = {}
    for budget in budgets:
        winners = {group: best(costs, scores, entries[budget]) for group, entries in eligible.items()}
        results[str(budget)] = {
            'settings': {group: {'setting': label, **totals[label]} for group, label in winners.items()},
            'passDelta': scores[winners['cpo']] - scores[winners['gepa']],
            'pairedCaseRange95': prior.frontier.interval(samples[budget]),
        }
    return results


def measure_cohort(plan, panels, anchors, archived, budgets):
    totals, subjects, vectors, traces = {}, {}, {}, {}
    modes = {}
    for _, subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        points, scores = prior.cost.measure_panel(subject, matrix, plan, anchors['panels'][panel])
        cpo_points, cpo_scores, traces[panel] = cpo_panel(subject, matrix, plan, anchors['panels'][panel]['holdoutCases'])
        modes = {'gepa': tuple(points), 'cpo': tuple(label for label in cpo_points if label != RETAIN)}
        grades_by_setting = {**scores, **cpo_scores}
        subject_points = subjects.setdefault(subject, {})
        subject_vectors = vectors.setdefault(subject, {})
        for label, value in {**points, **cpo_points}.items():
            totals.setdefault(label, Counter()).update(value)
            subject_points.setdefault(label, Counter()).update(value)
            grades = grades_by_setting[label]
            prior.add_vector(subject_vectors.setdefault(label, [0] * len(grades)), grades)
    full_cap = plan['maximumSweptCpoCap']
    original_vectors = {subject: {**{label: rows[label] for label in (*modes['gepa'], RETAIN)},
                                  **{label: rows[f'{label}/{full_cap}'] for label in prior.POLICIES}}
                        for subject, rows in vectors.items()}
    if (traces != archived['panelTraceSha256']
            or any(totals[f'{label}/{full_cap}'] != archived['totals'][label] for label in prior.POLICIES)
            or totals[RETAIN] != archived['totals'][RETAIN]
            or any(totals[label] != point for label, point in archived['nativeFrontier'].items())
            or digest(original_vectors) != archived['caseVectorsSha256']):
        raise ValueError('The published full-pool CPO paths and GEPA frontier must reproduce')
    if any(sum(sum(rows[label]) for rows in vectors.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('The paired case vectors must reconcile to every cap score')
    common = common_frontiers(vectors, totals, modes, budgets, plan)
    tuned = {group: prior.by_subject_ceiling(subjects, controls, {str(budget): budget for budget in budgets})
             for group, controls in modes.items()}
    for budget, row in common.items():
        for group in modes:
            if tuned[group][budget]['holdoutPasses'] < row['settings'][group]['holdoutPasses']:
                raise ValueError('The subject allocation must include every common setting')
        row['subjectTunedHindsight'] = {group: values[budget] for group, values in tuned.items()}
    return {'cpoFrontier': {label: totals[label] for label in (*modes['cpo'], RETAIN)},
            'atMatchedBudgets': common, 'caseVectorsSha256': digest(vectors)}


def replay(plan, panels, anchors, archived):
    cohorts = {cohort: measure_cohort(plan, [panel for panel in panels if panel[0] == cohort],
                                     anchors[cohort], row, plan['realizedCohortBudgets'][cohort])
               for cohort, row in archived.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'language': cohorts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
