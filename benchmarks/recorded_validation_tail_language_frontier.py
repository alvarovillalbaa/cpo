"""Match reserved validation cases to realized GEPA budgets on language panels."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import recorded_math_roster_ceiling as ceiling
from benchmarks import recorded_validation_tail_finalists as tail
from cpo._contract import digest


reference_runner = tail.prior
cost = tail.transfer.cost
frontier = cost.frontier
baseline = reference_runner.prior.NEVER
POLICIES = (baseline, *tail.TAILS)
REFERENCE = 'docs/recorded-validation-tail-finalists-results-v1.json'
REFERENCE_SHA256 = 'b8a7d62996b673aaf3a2022cf569eff9d4545a84fd5c47b872a4bddbc6c76227'


def prepare():
    inherited, inputs, _ = tail.prepare()
    receipt = cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    schedule, panels, native = inputs[-1]
    sources = (Path(__file__), Path(cost.__file__), Path(frontier.__file__))
    plan = {**{key: schedule[key] for key in ('gepaVersion', 'bootstrapSeed', 'bootstrapDraws', 'searchCap',
                                              'seeds', 'challengers', 'caseCounts')},
            'protocol': 'recorded-validation-tail-language-frontier-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'languagePlanSha256': digest(schedule),
            'panels': [panel[:3] for panel in panels], 'gepaModes': cost.MODES, 'policies': POLICIES,
            'minimumSearchCap': schedule['caseCounts'][1],
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'scope': 'Replay the same CPO deployments and holdout vectors on the original 26 language '
                     'panels. Sweep both native GEPA modes from the incumbent validation charge through '
                     'the original search cap. Match by realized search plus qualification. Reselect '
                     'the strongest affordable common cap on each paired case draw. Separately bound '
                     'the score with a different fixed cap per subject and shared cohort allowance, '
                     'using hindsight. Recover a fixed subject schedule that attains each bound.'}
    return plan, panels, native, receipt['language']


def add_vector(accumulator, values):
    for index, (old, new) in enumerate(zip(accumulator, values, strict=True)):
        accumulator[index] = old + new


def measure_panel(subject, matrix, plan, anchors):
    points, scores = cost.measure_panel(subject, matrix, plan, anchors)
    cells = {str(index): tuple((int(passed), None, False) for passed in vector) for index, vector in enumerate(matrix)}
    trace = {mode: [] for mode in POLICIES}
    for mode in (*POLICIES, frontier.RETAIN):
        points[mode] = Counter({'paidLookups': 0, 'holdoutPasses': 0})
        scores[mode] = [0] * anchors['holdoutCases']
    changes = {mode: Counter() for mode in tail.TAILS}
    for seed in plan['seeds']:
        start, roster, cohorts = reference_runner.language.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        args = (cells, start, roster, cohorts, seed, plan['searchCap'])
        before = reference_runner.prior.run_trial(*args, ())[:3]
        observations = {baseline: before, **{mode: tail.paired_trial(args, width, before, changes[mode])
                                              for mode, width in tail.TAILS.items()}}
        for mode, (point, decision, grades) in observations.items():
            points[mode].update(point)
            add_vector(scores[mode], grades)
            trace[mode].append(decision)
        keep = [cells[start][case][0] for case in cohorts[-1]]
        points[frontier.RETAIN]['holdoutPasses'] += sum(keep)
        add_vector(scores[frontier.RETAIN], keep)
    if any(sum(scores[mode]) != point['holdoutPasses'] for mode, point in points.items()):
        raise ValueError('Every candidate and native cap needs an exact held-out case vector')
    return points, scores, {mode: digest(paths) for mode, paths in trace.items()}


def by_subject_ceiling(available, controls, budgets):
    pooled = {0: 0}
    maximum_budget = max(budgets.values())
    stages = []
    for subject in sorted(available):
        options = {}
        for label in sorted((*controls, frontier.RETAIN)):
            point = available[subject][label]
            options.setdefault((point['holdoutPasses'], point['paidLookups']), label)
        nondominated = ceiling.extend({0: 0}, options)
        stages.append((subject, pooled, {(score, spend): options[score, spend] for score, spend in nondominated.items()}))
        pooled = {score: spend for score, spend in ceiling.extend(pooled, nondominated.items()).items()
                  if spend <= maximum_budget}
    result = {}
    for policy, budget in budgets.items():
        score = max(gain for gain, cost in pooled.items() if cost <= budget)
        need, spend = score, pooled[score]
        settings = {}
        for subject, preceding, options in reversed(stages):
            for (gain, price), label in options.items():
                if preceding.get(need - gain) == spend - price:
                    settings[subject] = label
                    need, spend = need - gain, spend - price
                    break
            else:
                raise ValueError('The subject ceiling requires an attaining fixed schedule')
        if need or spend:
            raise ValueError('Subject schedules must account for every pass and lookup')
        result[policy] = {'holdoutPasses': score, 'paidLookups': pooled[score], 'settingsBySubject': settings}
    return result


def measure_cohort(plan, panels, anchors, archived):
    totals, by_subject, vectors, traces = {}, {}, {}, {}
    for _, subject, model, matrix in panels:
        panel_name = f'{subject}/{model}'
        points, holdout, trace = measure_panel(subject, matrix, plan, anchors['panels'][panel_name])
        traces[panel_name] = trace
        subject_points, subject_vectors = by_subject.setdefault(subject, {}), vectors.setdefault(subject, {})
        for mode, point in points.items():
            totals.setdefault(mode, Counter()).update(point)
            subject_points.setdefault(mode, Counter()).update(point)
            add_vector(subject_vectors.setdefault(mode, [0] * len(holdout[mode])), holdout[mode])
    if any(totals[mode] != archived['totals'][mode] for mode in POLICIES):
        raise ValueError('The comparison must keep the published CPO policies and their realized budgets')
    for mode in cost.MODES:
        key = f"{mode}/{plan['searchCap']}"
        if (any(totals[key][metric] != archived['totals'][mode][metric] for metric in cost.METRICS)
                or any(rows[key] != anchors['caseVectorsBySubject'][subject][mode]
                       for subject, rows in vectors.items())):
            raise ValueError('The original native cap must reproduce its cost and held-out cases')
    if any(vectors[subject][frontier.RETAIN] != anchors['caseVectorsBySubject'][subject][frontier.RETAIN]
           for subject in vectors):
        raise ValueError('The zero-cost retained start must reproduce')
    controls = tuple(mode for mode in totals if mode not in (*POLICIES, frontier.RETAIN))
    measured = {mode: {key: total[key] for key in cost.METRICS} for mode, total in totals.items()}
    compared = frontier.compare(measured, vectors, policies=POLICIES, draws=plan['bootstrapDraws'],
                                seed=plan['bootstrapSeed'], groups={'gepa': controls})
    tuned_points = by_subject_ceiling(by_subject, controls, {mode: measured[mode]['paidLookups'] for mode in POLICIES})
    comparisons = {}
    for mode, row in compared.items():
        common_cap = row['gepa']
        tuned = tuned_points[mode]
        if tuned['holdoutPasses'] < common_cap['bestWithinCostPoint']['holdoutPasses']:
            raise ValueError('The subject-by-subject certificate must include every common setting')
        comparisons[mode] = {'commonCap': common_cap, 'subjectTunedHindsight': tuned,
                             'passDeltaAgainstSubjectTuned': measured[mode]['holdoutPasses'] - tuned['holdoutPasses']}
    return {'totals': {mode: measured[mode] for mode in (*POLICIES, frontier.RETAIN)},
            'nativeFrontier': {mode: measured[mode] for mode in controls},
            'comparisons': comparisons, 'panelTraceSha256': traces, 'caseVectorsSha256': digest(vectors)}


def replay(plan, panels, native, archived):
    results = {cohort: measure_cohort(plan, [panel for panel in panels if panel[0] == cohort],
                                     native[cohort], reference) for cohort, reference in archived.items()}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'language': results}


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
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
