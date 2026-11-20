"""Compare CPO validation policies with official GEPA at realized replay costs."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import case_difficulty_allocation as inputs
from benchmarks import family_qualification_order as ordered
from benchmarks import independent_mmlu_cost_uncertainty as uncertainty
from benchmarks import independent_witness_validation as guarded
from benchmarks import routed_score_allocation as route
from benchmarks.four_case_qualification_transfer import interval
from benchmarks.independent_mmlu_cost_frontier import CAPS, expect_reference
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
GUARD_REPORT = 'cb7859a9ad2a957095f4b38011b19d2184b7f6c85386d9793313546413e3f379'
CPO = ('strict', 'expected-order', *guarded.POLICIES)
MODES = tuple(label.split('/')[0] for label in route.PRIMARY)
GEPA = {mode: tuple(f'{mode}/{cap}' for cap in CAPS) for mode in MODES}
RETAIN = 'retain-start'


def prepare():
    source, cohorts = guarded.prepare()
    guards = inputs.checked_file('docs/independent-witness-validation-results-v1.json', GUARD_REPORT)
    ordering = inputs.checked_file('docs/family-qualification-order-results-v1.json', guarded.parent.SOURCE_REPORT)
    if guards['designSha256'] != digest(source) or ordering['designSha256'] != digest(ordered.prepare()[0]):
        raise ValueError('A CPO comparison differs from its published seal')
    paths = ('benchmarks/witness_validation_cost_frontier.py', 'benchmarks/independent_witness_validation.py',
             'benchmarks/family_qualification_order.py', 'benchmarks/gepa_paid_cap_transfer.py',
             'benchmarks/independent_mmlu_cost_frontier.py', 'benchmarks/independent_mmlu_cost_uncertainty.py',
             'benchmarks/four_case_qualification_transfer.py')
    design = {'protocol': 'cpo-witness-validation-cost-frontier-v1', 'guardDesignSha256': digest(source),
              'guardReportSha256': GUARD_REPORT, 'orderingReportSha256': guarded.parent.SOURCE_REPORT,
              'cpoMethods': CPO, 'gepaModes': MODES, 'gepaCaps': CAPS, 'bootstrapDraws': 4096,
              'bootstrapSeed': 20261129, 'reference': 'Same roster, starts, validation and qualification splits',
              'scope': ('Use realized search plus qualification lookups over each complete cohort. '
                        'Choose the highest-scoring affordable fixed GEPA mode and cap on every paired '
                        'case resample, keeping budgets and completed replay paths fixed.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, cohorts, guards['results'], ordering['results']


def measure_panel(panel, plan, guard_reference, order_reference):
    subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
    name = f'{subject}/{model}'
    held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
    schedule = plan['schedule']
    starts = route.ties.costs.retained_prompts(matrix, held, schedule)
    points, finals = {}, {}
    for label in CPO:
        total, traces = Counter(), []
        choose = []
        for seed, start in zip(schedule['seeds'], starts, strict=True):
            if label == 'expected-order':
                used, trace = ordered.run(matrix, held, seed, plan, str(start), 'strict', ordered=True)
            else:
                used, trace = guarded.episode(matrix, held, seed, plan, str(start), label)
            total.update(used)
            traces.append(trace)
            choose.append(int(trace[-1]['decision']['selected']))
        points[label] = {'holdoutPasses': total['holdoutPasses'],
                         'paidLookups': total['searchPaid'] + total['qualificationPaid'],
                         'traceSha256': digest(traces)}
        expected = order_reference['strict']['ordered'] if label == 'expected-order' else guard_reference[label]
        expect_reference(points[label], expected)
        finals[label] = choose

    for mode in MODES:
        for cap, label in zip(CAPS, GEPA[mode], strict=True):
            finals[label], points[label] = uncertainty.final_prompts(matrix, held, schedule, plan, mode, cap)
        label = f'{mode}/52'
        expect_reference(points[label], guard_reference[label])
    finals[RETAIN] = starts
    vectors = {label: tuple(uncertainty.case_totals(matrix, held, selected).values())
               for label, selected in finals.items()}
    points[RETAIN] = {'holdoutPasses': sum(vectors[RETAIN]), 'paidLookups': 0}
    if any(sum(vectors[label]) != point['holdoutPasses'] for label, point in points.items()):
        raise ValueError(f'The holdout vectors differ from the replay scores on {name}')
    return points, held, vectors


def highest_scoring(costs, scores, options):
    return min(options, key=lambda label: (-scores[label], costs[label], label))


def compare(totals, subjects, *, policies, draws, seed, groups):
    costs = {label: row['paidLookups'] for label, row in totals.items()}
    observed = {label: row['holdoutPasses'] for label, row in totals.items()}
    affordable = {policy: {group: tuple(label for label in (*options, RETAIN) if costs[label] <= costs[policy])
                           for group, options in groups.items()} for policy in policies}
    result = {policy: {} for policy in policies}
    samples = {(p, g): [] for p in policies for g in groups}
    choices = {key: Counter() for key in samples}
    labels = sorted(set(policies) | {label for item in affordable.values()
                                    for options in item.values() for label in options})
    rng = Random(seed)
    by_subject = [subjects[key] for key in sorted(subjects)]
    for _ in range(draws):
        score = Counter()
        for dataset in by_subject:
            size = len(dataset[RETAIN])
            weights = tuple(Counter(rng.randrange(size) for _ in range(size)).items())
            for label in labels:
                values = dataset[label]
                score[label] += sum(values[index] * multiplicity for index, multiplicity in weights)
        for policy, groups_to_check in affordable.items():
            for group, options in groups_to_check.items():
                winner = highest_scoring(costs, score, options)
                samples[policy, group].append(score[policy] - score[winner])
                choices[policy, group][winner] += 1

    for policy, groups_to_check in affordable.items():
        for group, options in groups_to_check.items():
            winner = highest_scoring(costs, observed, options)
            equal_quality = min((label for label in (*groups[group], RETAIN) if observed[label] >= observed[policy]),
                                key=lambda label: (costs[label], -observed[label], label), default=None)
            result[policy][group] = {
                'bestWithinCost': winner, 'bestWithinCostPoint': totals[winner],
                'holdoutPassDifference': observed[policy] - observed[winner],
                'pairedRange95': interval(samples[policy, group]),
                'resampledChoices': choices[policy, group],
                'cheapestMatching': equal_quality,
                'cheapestMatchingPoint': totals[equal_quality] if equal_quality is not None else None,
            }
    return result


def replay(design, panels, plan, guards, order_reference):
    details, totals, subjects, holdouts = {}, {}, {}, {}
    for panel in panels:
        subject, model = panel['subject'], panel['model']
        name = f'{subject}/{model}'
        points, held, vectors = measure_panel(panel, plan, guards['panels'][name], order_reference['panels'][name])
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both models must share the same ordered holdout cases')
        details[name] = points
        case_counts = subjects.setdefault(subject, {label: [0] * len(held) for label in points})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update({k: point[k] for k in ('holdoutPasses', 'paidLookups')})
            for idx, value in enumerate(vectors[label]):
                case_counts[label][idx] += value
    for label in CPO:
        expected = order_reference['totals']['strict']['ordered'] if label == 'expected-order' else guards['totals'][label]
        if any(total != expected[key] for key, total in totals[label].items()):
            raise ValueError('The pooled CPO totals differ from their recorded comparison')
    groups = {**GEPA, 'either-mode': tuple(label for options in GEPA.values() for label in options)}
    comparison = compare(totals, subjects, policies=CPO, draws=design['bootstrapDraws'],
                         seed=design['bootstrapSeed'], groups=groups)
    return {'totals': totals, 'comparisons': comparison, 'panels': details,
            'holdoutCasesBySubject': {subject: len(cases) for subject, cases in holdouts.items()}}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, cohorts, guards, ordering = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, plan, _ in cohorts.values()):
        cli.error('Use pinned GEPA 0.1.4')
    report = {}
    for name, (panels, plan, _) in cohorts.items():
        report[name] = replay(design, panels, plan, guards[name], ordering[name])
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': report}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
