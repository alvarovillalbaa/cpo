"""Transfer a shared probe that reserves one failed validation reply before certification."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_early_certificate_screen as prior
from cpo._contract import digest


cost, frontier, fixed = prior.cost, prior.frontier, prior.fixed
ROOT = fixed.archive.transfer.ROOT
PARENT = 'docs/recorded-early-certificate-screen-results-v1.json'
PARENT_SHA256 = 'f45d89bace132d6b51bdb2e340e484af544ee22ed40b2e4d7ea110b6d1d3a2e8'
DISCOVERY = 'docs/recorded-validation-tail-matched-caps-results-v1.json'
ARCHIVES = {
    'low-budget-transfer-v1.json': 'f28ec5f717137e179be0265b4236b1d034bebc5a1d1ce0273cbef56ab7c83d60',
    'late-miss-transfer-v1.json': '751ba960d8c8e8ed109316724a1fb0e988d2c841b7468cd8650b30228934f953',
    'posterior-model-transfer-v1.json': '6cefcc4ccc4d2dd197dcdff2294b178e14ccdd5de6819e03b66edf821b09efec',
}
CAP = 13
PRIMARY = 'one-failure/13'
METHODS = (PRIMARY, 'minimum-proof/13', 'complete-panel/13')


def enroll(entries, donors):
    donor_subjects = {subject for cohort, subject, _ in donors if cohort == 'MMLU'}
    donor_models = {model for _, _, model in donors}
    pairs, panels = {}, []
    for entry in entries:
        subject, model, matrix = (entry[key] for key in ('subject', 'model', 'correctness'))
        if subject in donor_subjects or model in donor_models:
            continue
        count = len(matrix[0])
        order, models = pairs.setdefault(subject, ((entry['caseOrderSha256'], count), set()))
        if (model in models or order != (entry['caseOrderSha256'], count)
                or len(matrix) != 100 or any(len(row) != count or set(row) - {'0', '1'} for row in matrix)):
            raise ValueError('The archived subject requires distinct, aligned 100-template panels')
        models.add(model)
        panels.append((subject, model, matrix))
    if not panels or any(len(models) != 2 for _, models in pairs.values()):
        raise ValueError('Each enrolled subject must retain both aligned model panels')
    return panels


def prepare():
    parent, *_ = prior.prepare()
    donor, *_ = fixed.fitted.prepare()
    read = cost.prior.baseline.read_reference
    read(PARENT, PARENT_SHA256, parent)
    read(DISCOVERY, fixed.DISCOVERY_SHA256, donor)
    entries = []
    for name, expected in ARCHIVES.items():
        data = (ROOT / 'benchmarks/data' / name).read_bytes()
        if sha256(data).hexdigest() != expected:
            raise ValueError('Use the exact published correctness snapshots')
        entries.extend(json.loads(data)['panels'])
    panels = enroll(entries, (*parent['enrolledPanels'], *donor['panels']))
    paths = (Path(__file__), Path(prior.__file__), Path(cost.__file__))
    plan = {**{key: parent[key] for key in ('caseCounts', 'seeds', 'challengers', 'searchCap',
                                          'minimumSearchCap', 'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-one-failure-screen-transfer-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': PARENT_SHA256,
            'discoveryReceiptSha256': fixed.DISCOVERY_SHA256, 'archivesSha256': ARCHIVES,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'enrolledPanels': [(subject, model) for subject, model, _ in panels],
            'methods': METHODS, 'candidate': PRIMARY, 'candidateSearchCap': CAP,
            'fixedCpoCaps': tuple(range(parent['minimumSearchCap'], (parent['challengers'] + 1) * parent['caseCounts'][1] + 1)),
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the highest-scoring '
                    'affordable fixed CPO setting, native GEPA setting, or retained starts',
            'scope': 'Freeze the first-miss probe and strict certificate at cap 13. Retain enough budget for '
                     'one failed post-probe reply if the full panel allows it. Compare with the published '
                     'minimum and full-panel reserves at cap 13. Use all aligned archived subject pairs whose '
                     'subjects and model checkpoints were absent from the cap discovery and earlier screen '
                     'comparison. Keep their seeded rosters and disjoint validation, proof and holdout. '
                     'Sweep all fixed CPO and native GEPA caps at realized search plus proof lookup costs.'}
    return plan, panels


def one_failure_trial(arguments):
    original = prior.select

    def choose(incumbent, candidates, rows, observe, ledger, *, cap, funding, audit):
        base = {row.id: observe(incumbent, row) for row in rows}
        target = 1 + sum(reply.passed for reply in base.values())
        reserve = min(len(rows) - 1, target)
        slots = max(0, cap - len(ledger) - reserve)

        def read(prompt, row):
            return base[row.id] if prompt == incumbent else observe(prompt, row)

        return original(incumbent, candidates[:slots], rows, read, ledger, cap=cap, funding=funding, audit=audit)

    with patch.object(prior, 'select', choose):
        return prior.trial(arguments, 'minimum-proof', CAP)


def measure_panel(subject, matrix, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    totals, vectors = {}, {}
    traces = {label: [] for label in METHODS}
    events = {label: Counter() for label in METHODS}
    native, native_traces = {label: Counter() for label in cost.MODES}, {label: [] for label in cost.MODES}
    for seed in plan['seeds']:
        start, roster, cohorts = fixed.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        heldout = [cells[start][case][0] for case in cohorts[-1]]
        measured = {frontier.RETAIN: ({'holdoutPasses': sum(heldout), 'paidLookups': 0}, heldout)}
        for cap in plan['fixedCpoCaps']:
            point, _, grades = fixed.fitted.cpo_trial(arguments, fixed.POLICY, cap)
            measured[f'{fixed.POLICY}/{cap}'] = point, grades
        for label in METHODS:
            if label == PRIMARY:
                point, trace, grades, audit = one_failure_trial(arguments)
            else:
                point, trace, grades, audit = prior.trial(arguments, label.split('/')[0], CAP)
            events[label].update(audit, nominations=int(trace[2] != start), promotions=int(trace[3] != start))
            traces[label].append(trace)
            measured[label] = point, grades
        for label, (point, grades) in measured.items():
            totals.setdefault(label, Counter()).update({key: point[key] for key in cost.METRICS})
            fixed.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(heldout)), grades)
        for mode in cost.MODES:
            point, trace, _ = cost.run(arguments, mode, plan['searchCap'])
            native[mode].update(point)
            native_traces[mode].append(trace)
    anchor = {mode: {**counts, 'traceSha256': digest(native_traces[mode])} for mode, counts in native.items()}
    gepa, native_scores = cost.measure_panel(subject, matrix, plan, {'totals': anchor, 'holdoutCases': len(heldout)})
    return ({**totals, **gepa}, {**vectors, **native_scores}, tuple(gepa),
            {'events': events, 'decisionTracesSha256': {label: digest(trace) for label, trace in traces.items()},
             'nativeAtOriginalCap': anchor, 'holdoutCases': len(heldout)})


def replay(plan, panels):
    totals, subjects, details = {}, {}, {}
    events = {label: Counter() for label in METHODS}
    for subject, model, matrix in panels:
        points, scores, gepa, detail = measure_panel(subject, matrix, plan)
        cases = subjects.setdefault(subject, {})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            grades = scores[label]
            fixed.fitted.prior.add_vector(cases.setdefault(label, [0] * len(grades)), grades)
        details[f'{subject}/{model}'] = detail
        for label, actual in detail['events'].items():
            events[label].update(actual)
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('Every fixed and screened point must reconcile to aligned cases')
    cpo = tuple(f'{fixed.POLICY}/{cap}' for cap in plan['fixedCpoCaps'])
    compared = frontier.compare(totals, subjects, policies=METHODS, draws=plan['bootstrapDraws'],
                                  seed=plan['bootstrapSeed'], groups={'fixed-cpo': cpo, 'fixed-gepa': gepa,
                                                                      'joint': (*cpo, *gepa)})
    joint = compared[PRIMARY]['joint']
    passed = joint['holdoutPassDifference'] > 0 and joint['pairedRange95'][0] >= 0
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'passedTransferGate': passed,
            'totals': totals, 'events': events, 'panels': details, 'comparison': compared,
            'caseVectorsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    result = replay(plan, panels)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
