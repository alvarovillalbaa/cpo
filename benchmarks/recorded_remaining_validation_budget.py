"""Test a strict improvement certificate in the unused budget of an exact validation race."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_paid_validation_continuation as prior
from cpo import challenger
from cpo._contract import digest


cost, frontier = prior.cost, prior.frontier
fixed = prior.prior
PARENT_RECEIPT = 'docs/recorded-paid-validation-continuation-results-v1.json'
PARENT_SHA256 = 'a78ff031f6a31bbabc0a4c25ea4ccb7fe1d49cd6a367e87eb56f700eec940f91'
CANDIDATES = {13: 'remaining-budget-certificate/13', 32: 'remaining-budget-certificate/32'}


def finish_validation(incumbent, leader, candidates, rows, observe, ledger, cap):
    before = len(ledger)
    allowance = cap - before
    if not 0 < allowance < len(rows):
        return leader
    baseline = {row.id: ledger[leader, row.id].passed for row in rows}
    if sum(baseline.values()) >= allowance:
        return leader
    # The original incumbent's critical passes remain mandatory after a lead change.
    ordered = tuple(replace(row, critical=row.critical and ledger[incumbent, row.id].passed)
                    for row in sorted(rows, key=lambda row: baseline[row.id]))
    seen = {prompt for prompt, _ in ledger}
    for prompt in candidates:
        if prompt in seen:
            continue
        decision = challenger.certify_challenger(ordered, baseline, lambda row: observe(prompt, row),
                                                 metric_limit=cap - len(ledger))
        if decision.status == 'promote':
            return prompt
        if decision.status == 'budget':
            break
    return leader


def certificate_trial(arguments, cap):
    original = prior.math.select
    audit = Counter()
    remainder = None

    def choose(incumbent, candidates, rows, observe, ledger, *, method, cap):
        nonlocal remainder
        leader, tied = original(incumbent, candidates, rows, observe, ledger, method=method, cap=cap)
        if tied:
            raise ValueError('The remainder certificate requires an exactly scored strict leader')
        before = len(ledger)
        if 0 < cap - before < len(rows):
            seen = {prompt for prompt, _ in ledger}
            remainder = (leader, tuple(prompt for prompt in candidates if prompt not in seen), cap - before,
                         tuple(int(row.id) for row in rows if row.critical and ledger[incumbent, row.id].passed))
        chosen = finish_validation(incumbent, leader, candidates, rows, observe, ledger, cap)
        audit.update(certificateLookups=len(ledger) - before, attempts=int(len(ledger) > before),
                     changedNominations=int(chosen != leader))
        return chosen, False

    with patch.object(prior.math, 'select', choose):
        outcome = fixed.fitted.cpo_trial(arguments, fixed.POLICY, cap)
    return outcome, audit, remainder


def hindsight_headroom(arguments, remainder, baseline_passes):
    """Bound improvements with the exact prefix fixed and all future grades known."""
    if remainder is None:
        return {}
    cells, incumbent, _, (_, validation, qualification, heldout), _ = arguments
    leader, unread, allowance, protected = remainder
    target = 1 + sum(cells[leader][case][0] for case in validation)
    if not unread or target > allowance:
        return {}
    feasible = [prompt for prompt in unread if sum(cells[prompt][case][0] for case in validation) >= target
                and all(cells[prompt][case][0] for case in protected)]
    qualified = [prompt for prompt in feasible if sum(cells[prompt][case][0] - cells[incumbent][case][0]
                                                      for case in qualification) > 0]
    best = max((sum(cells[prompt][case][0] for case in heldout) for prompt in qualified), default=baseline_passes)
    return {'trialsWithFundableCertificate': int(bool(feasible)),
            'trialsWithFundableQualifiedCertificate': int(bool(qualified)),
            'extraPassesWithHindsight': max(0, best - baseline_passes)}


def prepare():
    source, panels, native, reference = prior.prepare()
    parent = cost.prior.baseline.read_reference(PARENT_RECEIPT, PARENT_SHA256, source)
    paths = (Path(__file__), Path(prior.__file__), Path(challenger.__file__), Path(prior.pool.__file__))
    plan = {**source, 'protocol': 'recorded-remaining-validation-budget-v1', 'parentPlanSha256': digest(source),
            'parentReceiptSha256': PARENT_SHA256, 'sourceSha256': {
                path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'candidate': CANDIDATES[13], 'certificateSettings': CANDIDATES,
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the strongest '
                    'affordable fixed-cap CPO, GEPA or retained starts at cap 13',
            'scope': 'Run the original exact race. If the remaining allowance cannot fund an exact candidate, '
                     'consider still-unread challengers in roster order. Stop as soon as a strict certificate '
                     'over the exact leader preserves all original protected passes. Compare caps 13 and 32 '
                     'with the fixed CPO and native GEPA curves, preserving the single independent qualification. '
                     'After replay, bound the gain with the exact prefix fixed and perfect knowledge of '
                     'unread validation, qualification, and holdout outcomes. These held-out cases were '
                     'used by the cap-13 transfer and continuation studies.'}
    return plan, panels, native, parent, reference


def measure_cpo(subject, matrix, plan):
    points, scores, baseline_routes, exact_paths = prior.measure_cpo(subject, matrix, plan)
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    stats = {name: Counter() for name in CANDIDATES.values()}
    logs = {name: [] for name in CANDIDATES.values()}
    for seed in plan['seeds']:
        start, roster, cohorts = fixed.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        for cap, label in CANDIDATES.items():
            baseline, before, original_grades = fixed.fitted.cpo_trial(arguments, fixed.POLICY, cap)
            (point, trace, grades), audit, remainder = certificate_trial(arguments, cap)
            if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(cohorts[2])
                    or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']
                    or point['searchLookups'] != baseline['searchLookups'] + audit['certificateLookups']):
                raise ValueError('The final certificate must fit the original search and proof envelopes')
            if audit['certificateLookups'] == 0 and (point, trace, grades) != (baseline, before, original_grades):
                raise ValueError('A trial with no added evidence must keep the exact original path')
            if trace[2] != before[2] and sum(cells[trace[2]][case][0] - cells[before[2]][case][0]
                                             for case in cohorts[1]) <= 0:
                raise ValueError('A different nominee must strictly beat the exact validation leader')
            if trace[3] != start and (trace[3] != trace[2] or
                    sum(cells[trace[3]][case][0] - cells[start][case][0] for case in cohorts[2]) <= 0):
                raise ValueError('A deployment must qualify the same nominee independently')
            points.setdefault(label, Counter()).update({key: point[key] for key in cost.METRICS})
            fixed.fitted.prior.add_vector(scores.setdefault(label, [0] * len(grades)), grades)
            stats[label].update(audit, changedDeployments=int(trace[3] != before[3]),
                                passDelta=point['holdoutPasses'] - baseline['holdoutPasses'],
                                extraPaidLookups=point['paidLookups'] - baseline['paidLookups'])
            stats[label].update(hindsight_headroom(arguments, remainder, baseline['holdoutPasses']))
            logs[label].append(trace)
    return points, scores, stats, {name: digest(trace) for name, trace in logs.items()}, baseline_routes, exact_paths


def replay(plan, panels, native, parent, reference):
    totals, subjects, details = {}, {}, {}
    stats = {name: Counter() for name in CANDIDATES.values()}
    for _, subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        cpo, scores, audit, traces, routes, exact = measure_cpo(subject, matrix, plan)
        if {'fixedCapTracesSha256': exact, 'routes': routes} != parent['panels'][panel]:
            raise ValueError('The prior endpoints and continuation paths must reproduce on each panel')
        gepa, native_scores = cost.measure_panel(
            subject, matrix, plan, {'totals': native['panelsAtOriginalCap'][panel],
                                    'holdoutCases': len(scores[frontier.RETAIN])})
        merged_scores = {**scores, **native_scores}
        rows = subjects.setdefault(subject, {})
        for label, point in {**cpo, **gepa}.items():
            totals.setdefault(label, Counter()).update(point)
            grades = merged_scores[label]
            fixed.fitted.prior.add_vector(rows.setdefault(label, [0] * len(grades)), grades)
        for label, counts in audit.items():
            stats[label].update(counts)
        details[panel] = {'counts': audit, 'policyTracesSha256': traces}
    if (any(totals[label] != reference['totals'][label] for label in gepa)
            or any(totals[label] != point for label, point in parent['totals'].items())):
        raise ValueError('The previously measured native and fixed CPO frontiers must reproduce')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('Each point must reconcile to its paired case vectors')
    fixed_cpo = tuple(f'{fixed.POLICY}/{cap}' for cap in plan['fixedCpoCaps'])
    comparison = frontier.compare(totals, subjects, policies=tuple(CANDIDATES.values()), draws=plan['bootstrapDraws'],
                                  seed=plan['bootstrapSeed'],
                                  groups={'fixed-cpo': fixed_cpo, 'fixed-gepa': tuple(gepa),
                                          'joint': (*fixed_cpo, *gepa)})
    joint = comparison[CANDIDATES[13]]['joint']
    passed = joint['holdoutPassDifference'] > 0 and joint['pairedRange95'][0] >= 0
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'passedArchiveGate': passed,
            'totals': {label: totals[label] for label in CANDIDATES.values()}, 'changes': stats,
            'comparison': comparison, 'panels': details, 'caseVectorsSha256': digest(subjects)}


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
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
