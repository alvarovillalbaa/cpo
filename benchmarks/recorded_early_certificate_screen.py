"""Compare two ways to fund a shared validation probe before an exact certificate."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_remaining_validation_budget as prior
from cpo import challenger
from cpo._contract import digest


cost, frontier = prior.cost, prior.frontier
fixed, ordered = prior.fixed, prior.prior
calibrated = fixed.fitted.prior.reference_runner.prior
PARENT = 'docs/recorded-remaining-validation-budget-results-v1.json'
PARENT_SHA256 = 'e42ac62f5f0777c0fd8969a880c405277af3631fdd0f141dc63a3213fd02caa7'
FUNDING = ('minimum-proof', 'complete-panel')
CAPS = (13, 32)
METHODS = {f'{funding}/{cap}': (funding, cap) for cap in CAPS for funding in FUNDING}
PRIMARY = 'minimum-proof/13'


def select(incumbent, candidates, rows, observe, ledger, *, cap, funding, audit):
    base = {row.id: observe(incumbent, row).passed for row in rows}
    witness = next((row for row in rows if not base[row.id]), None)
    if witness is None:
        return incumbent
    target = sum(base.values()) + 1
    reserve = (target if funding == 'minimum-proof' else len(rows)) - 1
    slots = max(0, cap - len(ledger) - reserve)
    initial = {prompt: observe(prompt, witness).passed for prompt in candidates[:slots]}
    audit['screenLookups'] += len(initial)
    order = sorted(rows, key=lambda row: base[row.id])
    for prompt, passed in sorted(initial.items(), key=lambda row: row[1], reverse=True):
        before = len(ledger)
        decision = challenger.certify_challenger(order, base, lambda row: observe(prompt, row),
                                                 metric_limit=cap - before, observed={witness.id: passed})
        audit['certificateLookups'] += len(ledger) - before
        if decision.status == 'promote':
            return prompt
    return incumbent


def trial(arguments, funding, cap):
    audit = Counter()

    def choose(incumbent, candidates, rows, observe, ledger, **_settings):
        winner = select(incumbent, candidates, rows, observe, ledger, cap=cap, funding=funding, audit=audit)
        return winner, False

    # The disabled training route still expects fully scored validation panels.
    # Use the validation-only path so a partial certificate can qualify.
    with (patch.object(ordered.math, 'select', choose),
          patch.object(calibrated.core.prior, 'can_defer', lambda *_: False),
          patch.object(calibrated.core.backup, 'select_with_training', lambda _, first, *args, **kwargs: first)):
        point, trace, grades = calibrated.adapter.run_trial(*arguments, cap, calibrated.parent.BASELINE,
                                                             calibrated.adapter.EXPECTED)
    cells, incumbent, _, (_, validation, qualification, _), _ = arguments
    if (point['searchLookups'] > cap or point['qualificationLookups'] > 2 * len(qualification)
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
        raise ValueError('The screen and certificate must fit the existing lookup caps')
    if trace[2] != incumbent and sum(cells[trace[2]][case][0] - cells[incumbent][case][0] for case in validation) <= 0:
        raise ValueError('A finalist must show a strict validation gain')
    if trace[3] != incumbent and (trace[3] != trace[2] or
            sum(cells[trace[3]][case][0] - cells[incumbent][case][0] for case in qualification) <= 0):
        raise ValueError('The same finalist must qualify independently')
    return point, trace, grades, audit


def prepare():
    source, panels, native, previous, reference = prior.prepare()
    bound = cost.prior.baseline.read_reference(PARENT, PARENT_SHA256, source)
    paths = (Path(__file__), Path(prior.__file__), Path(challenger.__file__), Path(calibrated.adapter.__file__))
    plan = {**source, 'protocol': 'recorded-early-certificate-screen-v1',
            'parentPlanSha256': digest(source), 'parentReceiptSha256': PARENT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'methods': METHODS, 'candidate': PRIMARY,
            'gate': 'positive observed margin and nonnegative paired lower endpoint against affordable fixed-cap '
                    'CPO, native GEPA, or retained starts for the minimum-proof cap-13 primary',
            'scope': 'Pay for the incumbent, screen the largest affordable prefix of the roster on its first '
                     'miss, and visit screened challengers with passes first. Reserve either the minimum '
                     'favorable reads to certify a strict gain or a complete finalist panel, crediting the '
                     'probe in both cases. Stop at the first strict protected certificate and qualify the '
                     'nominee once. Reuse the earlier 896 MMLU trials and match by realized lookup cost.'}
    return plan, panels, native, previous, reference, bound


def measure_cpo(subject, matrix, plan):
    counts, vectors, routes, exact = ordered.measure_cpo(subject, matrix, plan)
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    events, traces = {label: Counter() for label in METHODS}, {label: [] for label in METHODS}
    for seed in plan['seeds']:
        start, roster, cohorts = fixed.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        for label, (funding, cap) in METHODS.items():
            point, trace, grades, audit = trial(arguments, funding, cap)
            counts.setdefault(label, Counter()).update({key: point[key] for key in cost.METRICS})
            fixed.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)
            events[label].update(audit, nominations=int(trace[2] != start), promotions=int(trace[3] != start))
            traces[label].append(trace)
    return counts, vectors, events, {label: digest(log) for label, log in traces.items()}, routes, exact


def replay(plan, panels, native, previous, reference, bound):
    totals, subjects, details = {}, {}, {}
    events = {label: Counter() for label in METHODS}
    for _, subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        cpo, scores, observed, hashes, routes, exact = measure_cpo(subject, matrix, plan)
        if {'fixedCapTracesSha256': exact, 'routes': routes} != previous['panels'][panel]:
            raise ValueError('Both fixed endpoint traces and prior continuation paths must reproduce')
        gepa, native_scores = cost.measure_panel(
            subject, matrix, plan, {'totals': native['panelsAtOriginalCap'][panel],
                                    'holdoutCases': len(scores[frontier.RETAIN])})
        available = {**scores, **native_scores}
        rows = subjects.setdefault(subject, {})
        for label, point in {**cpo, **gepa}.items():
            totals.setdefault(label, Counter()).update(point)
            grades = available[label]
            fixed.fitted.prior.add_vector(rows.setdefault(label, [0] * len(grades)), grades)
        for label, actual in observed.items():
            events[label].update(actual)
        details[panel] = {'events': observed, 'decisionTracesSha256': hashes}
    if (any(totals[label] != reference['totals'][label] for label in gepa)
            or any(totals[label] != point for label, point in previous['totals'].items())
            or any(totals[f'{fixed.POLICY}/{cap}']['holdoutPasses'] != bound['totals'][prior.CANDIDATES[cap]]['holdoutPasses']
                   for cap in CAPS)):
        raise ValueError('The fixed-cap GEPA and CPO points must reproduce')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('The point scores must match their paired vectors')
    fixed_controls = tuple(f'{fixed.POLICY}/{cap}' for cap in plan['fixedCpoCaps'])
    comparison = frontier.compare(totals, subjects, policies=tuple(METHODS), draws=plan['bootstrapDraws'],
                                  seed=plan['bootstrapSeed'], groups={'fixed-cpo': fixed_controls,
                                                                      'fixed-gepa': tuple(gepa),
                                                                      'joint': (*fixed_controls, *gepa)})
    joint = comparison[PRIMARY]['joint']
    passed = joint['holdoutPassDifference'] > 0 and joint['pairedRange95'][0] >= 0
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'passedArchiveGate': passed,
            'totals': {label: totals[label] for label in METHODS}, 'events': events, 'comparison': comparison,
            'panels': details, 'caseVectorsSha256': digest(subjects)}


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
