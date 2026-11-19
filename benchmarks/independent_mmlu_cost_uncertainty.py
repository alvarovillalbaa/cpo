"""Resample paired holdout cases and reselect the affordable GEPA control."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import independent_mmlu_transfer as transfer
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
REPORT_SHA256 = '1038005684d3475e4cf05f593423f6e4e7e3c71058b006c16a0c82ba04938efa'
CPO_CAPS = (28, 52)
DRAWS = 4096
BOOTSTRAP_SEED = 20261119
MODES = transfer.gepa.METHODS


def prepare():
    previous, schedules, data, *_ = frontier.prepare()
    raw = (ROOT / 'docs/independent-mmlu-cost-frontier-results-v1.json').read_bytes()
    report = transfer.read_json(raw)
    if sha256(raw).hexdigest() != REPORT_SHA256 or report['planSha256'] != digest(previous):
        raise ValueError('The original frontier differs from its sealed replay')
    cpo = {label: report['cpoTotals'][label]['paidLookups'] for label in (f'seeded-{cap}' for cap in CPO_CAPS)}
    fixed = {f'{method}/{cap}': row['paidLookups'] for method, points in report['gepaTotals'].items()
             for cap, row in points.items() if row['paidLookups'] <= max(cpo.values())}
    matches = {}
    for name in cpo:
        match = report['matchedCostComparisons'][name]['cheapestFixedGepaMatchingPasses']
        choice = f"{match['method']}/{match['cap']}"
        fixed[choice] = match['paidLookups']
        matches[name] = choice
    plan = {
        'protocol': 'cpo-independent-mmlu-cost-uncertainty-v1', 'frontierPlanSha256': digest(previous),
        'frontierReportSha256': REPORT_SHA256, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'corpusSha256': previous['corpusSha256'], 'gepaVersion': previous['gepaVersion'],
        'validationRows': previous['validationRows'], 'bootstrapDraws': DRAWS, 'bootstrapSeed': BOOTSTRAP_SEED,
        'cpoPaidLookups': cpo, 'gepaPaidLookups': fixed, 'publishedScoreMatchedGepa': matches,
        'resample': ('Draw held-out case IDs with replacement within each subject. For each sampled case '
                     'include both model panels and all original episodes. Reselect the highest-scoring '
                     'affordable fixed GEPA point in every draw. Search and budgets stay fixed.'),
        'interval': 'Central empirical 95 percent sensitivity interval, conditional on the archived subjects and paths.',
        'comparisonThreshold': 'Zero holdout pass difference at the reported paid cost.',
    }
    return plan, schedules, data, report


def final_prompts(matrix, held, schedules, plan, method, cap):
    settings = {'searchCap': cap, 'validationRows': plan['validationRows']}
    finals, traces, prices = [], [], Counter()
    for seed in schedules['seeds']:
        if method == transfer.gepa.CPO:
            costs, trace = archive.episode(matrix, held, seed, schedules, settings, 'recency')
            final = trace[-1]['decision']['selected']
        else:
            final, costs, peak, trace = transfer.gepa.reinvest_episode(
                matrix, held, seed, schedules, settings, batched=method == MODES[1])
            if peak > cap:
                raise ValueError('GEPA exceeded the sealed paid search cap')
        finals.append(int(final))
        traces.append(trace)
        prices.update(costs)
    point = {'holdoutPasses': prices['holdoutPasses'], 'paidLookups': prices['searchPaid'] + prices['qualificationPaid'],
             'traceSha256': digest(traces)}
    return finals, point


def case_totals(matrix, held, finals):
    frequencies = Counter(finals)
    return {case: sum(count for prompt, count in frequencies.items() if matrix[prompt][case] == '1') for case in held}


def collect_cases(plan, schedules, data, report):
    subjects = {}
    for item in data:
        subject, model, matrix = (item[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        archived = report['panels'][name]
        held = schedules['holdoutCaseIDs'][subject]
        points = {name: (transfer.gepa.CPO, int(name.split('-')[-1]), archived['cpo'][name])
                  for name in plan['cpoPaidLookups']}
        for label in plan['gepaPaidLookups']:
            mode, cap = label.split('/')
            points[label] = mode, int(cap), archived['gepa'][mode][cap]
        panel_counts = {}
        for label, (mode, cap, expected) in points.items():
            finals, point = final_prompts(matrix, held, schedules, plan, mode, cap)
            frontier.expect_reference(point, expected)
            panel_counts[label] = case_totals(matrix, held, finals)
            if sum(panel_counts[label].values()) != expected['holdoutPasses']:
                raise ValueError('Case counts do not reproduce the archived holdout total')
        starts = [int(archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, schedules)[0])
                  for seed in schedules['seeds']]
        panel_counts['retain-start'] = case_totals(matrix, held, starts)
        if sum(panel_counts['retain-start'].values()) != archived['retainStart']:
            raise ValueError('The retained start totals differ')
        union = subjects.setdefault(subject, {case: Counter() for case in held})
        if tuple(union) != tuple(panel_counts['retain-start']):
            raise ValueError('Both model panels must share the same ordered holdout cases')
        for label, counts in panel_counts.items():
            for case, count in counts.items():
                union[case][label] += count
    return {subject: [dict(row) for row in cases.values()] for subject, cases in subjects.items()}


def deltas(totals, plan):
    gaps, winners = {}, {}
    for method, cost in plan['cpoPaidLookups'].items():
        fixed = min((choice for choice, paid in plan['gepaPaidLookups'].items() if paid <= cost),
                    key=lambda choice: (-totals[choice], plan['gepaPaidLookups'][choice], choice))
        winners[method] = fixed
        matched = plan['publishedScoreMatchedGepa'][method]
        for control, name in ((fixed, 'affordable'), (matched, 'score-matched'), ('retain-start', 'retain-start')):
            gaps[f'{method}/{name}'] = totals[method] - totals[control]
    return gaps, winners


def resample(subjects, plan):
    rng = Random(plan['bootstrapSeed'])
    labels = (*plan['cpoPaidLookups'], *plan['gepaPaidLookups'], 'retain-start')
    samples = {label: [] for label in deltas(Counter(dict.fromkeys(labels, 0)), plan)[0]}
    winners = {method: Counter() for method in plan['cpoPaidLookups']}
    vectors = []
    for subject in sorted(subjects):
        rows = subjects[subject]
        vectors.append({label: tuple(row[label] for row in rows) for label in labels})
    for _ in range(plan['bootstrapDraws']):
        totals = Counter()
        for vector in vectors:
            size = len(vector[labels[0]])
            weights = Counter(rng.randrange(size) for _ in range(size))
            for label, scores in vector.items():
                totals[label] += sum(scores[i] * count for i, count in weights.items())
        draw, selected = deltas(totals, plan)
        for label, gap in draw.items():
            samples[label].append(gap)
        for method, option in selected.items():
            winners[method][option] += 1
    return samples, winners


def summarize(plan, subjects):
    totals = Counter()
    for rows in subjects.values():
        for row in rows:
            totals.update(row)
    observed, affordable = deltas(totals, plan)
    samples, winners = resample(subjects, plan)
    results = {}
    for name, draw in samples.items():
        ordered = sorted(draw)
        results[name] = {'observedPassDifference': observed[name],
                         'interval95PassDifferences': [ordered[(len(draw) - 1) * q // 1000] for q in (25, 975)],
                         'drawsCpoHigher': sum(v > 0 for v in draw), 'drawsTied': draw.count(0),
                         'drawsCpoLower': sum(v < 0 for v in draw)}
    return {'observedTotals': dict(totals), 'affordableGepaAtObservedScores': affordable,
            'affordableGepaSelections': winners, 'comparisons': results,
            'distinctCasesBySubject': {subject: len(rows) for subject, rows in subjects.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, schedules, data, archived = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    cases = collect_cases(plan, schedules, data, archived)
    report = {'plan': plan, 'planSha256': seal, **summarize(plan, cases)}
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
