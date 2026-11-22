"""Test continuation from a paid validation signal before independent qualification."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_low_cap_mmlu_transfer as prior
from cpo import pool
from cpo._contract import digest


math = prior.fitted.prior.reference_runner.math
cost, frontier = prior.cost, prior.frontier
REFERENCE = 'docs/recorded-low-cap-mmlu-transfer-results-v1.json'
REFERENCE_SHA256 = '35da1bc739556d0743975c20780d5775ca39745bfe27f6214a967f693e414a73'
LOW, FULL = 13, 54
PAID = 'continue-on-paid-paired-win'
BLIND = 'continue-after-no-nomination'
ROUTES = (PAID, BLIND)


def has_paired_win(incumbent, candidates, rows, ledger):
    for prompt in candidates:
        differences = [ledger[prompt, row.id].passed - ledger[incumbent, row.id].passed
                       for row in rows if (prompt, row.id) in ledger and (incumbent, row.id) in ledger]
        if 1 in differences and sum(differences) >= 0:
            return True
    return False


def routed_trial(arguments, route):
    original = math.select
    continued = False

    def choose(incumbent, candidates, rows, observe, ledger, *, method, cap):
        nonlocal continued
        nominee, tied = original(incumbent, candidates, rows, observe, ledger, method=method, cap=LOW)
        if nominee == incumbent and (route == BLIND or has_paired_win(incumbent, candidates, rows, ledger)):
            # Re-enter the exact race through the same evaluator and paid ledger.
            before = len(ledger)
            nominee, tied = original(incumbent, candidates, rows, observe, ledger, method=method, cap=cap)
            continued = len(ledger) > before
        return nominee, tied

    with patch.object(math, 'select', choose):
        outcome = prior.fitted.cpo_trial(arguments, prior.POLICY, FULL)
    return outcome, continued


def prepare():
    base, panels, native = prior.prepare()
    receipt = cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, base)
    paths = (Path(__file__), Path(prior.__file__), Path(math.__file__), Path(pool.__file__))
    plan = {**base, 'protocol': 'recorded-paid-validation-continuation-v1',
            'parentPlanSha256': digest(base), 'parentReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'candidate': PAID, 'routeControl': BLIND, 'fixedCpoCaps': tuple(range(LOW, FULL + 1)),
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the best '
                    'affordable setting from fixed CPO, GEPA, or retaining starts',
            'scope': 'Reuse the cap-13 validation observations and choose whether to fund the full pool '
                     'before selecting a single nominee for independent qualification. Continue only after '
                     'no nomination and an already-observed paired win without net paired loss. Compare '
                     'against continuing after any failed nomination, all fixed CPO caps 13 through 54, '
                     'and the original native controls at realized costs. This is exploratory archive reuse.'}
    return plan, panels, native, receipt


def measure_cpo(subject, matrix, plan):
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    totals, vectors, routes = {}, {}, {route: Counter() for route in ROUTES}
    decisions = []
    for seed in plan['seeds']:
        start, roster, cohorts = prior.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        holdout = [cells[start][case][0] for case in cohorts[-1]]
        fixed = {cap: prior.fitted.cpo_trial(arguments, prior.POLICY, cap) for cap in plan['fixedCpoCaps']}
        measured = {f'{prior.POLICY}/{cap}': outcome for cap, outcome in fixed.items()}
        measured[frontier.RETAIN] = ({'holdoutPasses': sum(holdout), 'paidLookups': 0}, None, holdout)
        decisions.append((fixed[LOW][1], fixed[FULL][1]))
        for route in ROUTES:
            result, extended = routed_trial(arguments, route)
            expected = fixed[FULL] if extended else fixed[LOW]
            if result != expected:
                raise ValueError('Every route must exactly reuse one of the two validation and proof paths')
            routes[route].update(expandedTrials=int(extended),
                                 changedDeployments=int(result[1][3] != fixed[LOW][1][3]),
                                 extraLookups=result[0]['paidLookups'] - fixed[LOW][0]['paidLookups'],
                                 passDelta=result[0]['holdoutPasses'] - fixed[LOW][0]['holdoutPasses'])
            measured[route] = result
        for label, (point, _, grades) in measured.items():
            totals.setdefault(label, Counter()).update({key: point[key] for key in cost.METRICS})
            prior.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(holdout)), grades)
    return totals, vectors, routes, digest(decisions)


def replay(plan, panels, native, receipt):
    totals, subjects, details = {}, {}, {}
    routes = {route: Counter() for route in ROUTES}
    for _, subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        cpo, scores, changed, trace = measure_cpo(subject, matrix, plan)
        archived = receipt['panels'][panel]
        for label in (prior.PRIMARY, prior.FULL, frontier.RETAIN):
            if any(cpo[label][key] != archived['cpo'][label][key] for key in cost.METRICS):
                raise ValueError('The archived fixed CPO points must reproduce on each panel')
        if trace != archived['decisionsSha256']:
            raise ValueError('The two endpoint decision traces must reproduce')
        gepa, native_scores = cost.measure_panel(
            subject, matrix, plan, {'totals': native['panelsAtOriginalCap'][panel],
                                    'holdoutCases': len(scores[frontier.RETAIN])})
        controls = tuple(gepa)
        merged_scores = {**scores, **native_scores}
        rows = subjects.setdefault(subject, {})
        for label, point in {**cpo, **gepa}.items():
            totals.setdefault(label, Counter()).update(point)
            grades = merged_scores[label]
            prior.fitted.prior.add_vector(rows.setdefault(label, [0] * len(grades)), grades)
        for route, counts in changed.items():
            routes[route].update(counts)
        details[panel] = {'fixedCapTracesSha256': trace, 'routes': changed}
    if any(totals[label] != receipt['totals'][label] for label in controls):
        raise ValueError('The native GEPA curve must reproduce')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('Every paired case vector must match the corresponding point score')
    cpo_controls = tuple(f'{prior.POLICY}/{cap}' for cap in plan['fixedCpoCaps'])
    comparison = frontier.compare(totals, subjects, policies=ROUTES, draws=plan['bootstrapDraws'],
                                  seed=plan['bootstrapSeed'],
                                  groups={'fixed-cpo': cpo_controls, 'fixed-gepa': controls,
                                          'joint': (*cpo_controls, *controls)})
    joint = comparison[PAID]['joint']
    passed = joint['holdoutPassDifference'] > 0 and joint['pairedRange95'][0] >= 0
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'passedArchiveGate': passed,
            'totals': {label: totals[label] for label in (*ROUTES, *cpo_controls, frontier.RETAIN)},
            'continuation': routes, 'comparison': comparison, 'panels': details,
            'caseVectorsSha256': digest(subjects)}


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
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
