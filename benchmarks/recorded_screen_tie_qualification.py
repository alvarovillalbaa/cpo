"""Admit a witnessed validation tie to strict independent qualification."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_screen_coverage_ceiling as source
from benchmarks import routed_validation_ties as ties
from cpo._contract import digest


prior = source.prior
early, cost, frontier = prior.prior, prior.cost, prior.frontier
RECEIPT = 'docs/recorded-screen-coverage-ceiling-results-v1.json'
RECEIPT_SHA256 = 'ba6b3abacbb68323bbf7c78cf2f4d00cf60043bb70682633ec0f95df6820e0c0'
BASELINE = 'complete-panel/13'
POLICIES = {'paid-witnessed-tie': 0, 'finish-two-witnessed-tie': 2}
PRIMARY = 'finish-two-witnessed-tie'


def prepare():
    parent, panels, transfer = source.prepare()
    receipt = cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, parent)
    paths = (Path(__file__), Path(source.__file__), Path(ties.__file__))
    plan = {**parent, 'protocol': 'recorded-screen-tie-qualification-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'candidate': PRIMARY, 'extraValidationLimits': POLICIES,
            'gate': 'positive observed margin and nonnegative paired lower endpoint against the best affordable '
                    'fixed CPO, native GEPA, published cap-13 screen, or retained start',
            'scope': 'Keep the cap-13 complete-panel screen and any strict nominee. If none qualifies for '
                     'nomination, consider a previously witnessed validation tie and finish it using at '
                     'most two of the unused lookups. Preserve critical passes and strict independent '
                     'qualification. Reuse the archived transfer, including paired fixed CPO and GEPA curves.'}
    return plan, panels, transfer, receipt


def trial(arguments, additional):
    calibrated, math = early.calibrated, early.ordered.math
    audit = Counter()

    def select(incumbent, candidates, rows, observe, ledger, *, method, cap):
        nominee = early.select(incumbent, candidates, rows, observe, ledger,
                               cap=cap, funding='complete-panel', audit=audit)
        if nominee != incumbent:
            return nominee, False
        before = len(ledger)
        tied = ties.certified_tie(incumbent, candidates, rows, ledger, observe, extra=additional, metric_limit=cap)
        audit.update(tieLookups=len(ledger) - before, tieNominations=int(tied is not None))
        return tied or incumbent, tied is not None

    with (patch.object(math, 'select', select),
          patch.object(calibrated.core.prior, 'can_defer', lambda *_: False),
          patch.object(calibrated.core.backup, 'select_with_training', lambda _, first, *args, **kwargs: first)):
        point, trace, grades = calibrated.adapter.run_trial(*arguments, prior.CAP, calibrated.parent.BASELINE,
                                                             calibrated.adapter.EXPECTED)
    cells, start, _, (_, validation, proof, _), _ = arguments
    if (point['searchLookups'] > prior.CAP or point['qualificationLookups'] > 2 * len(proof)
            or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']
            or audit['tieLookups'] > additional):
        raise ValueError('Validation and qualification must fit their original lookup budgets')
    nominee, deployed = trace[2:4]
    # The shared training adapter forwards the selected prompt and drops its tie flag.
    point['tieNominations'] = audit['tieNominations']
    point['tiePromotions'] = int(bool(audit['tieNominations']) and deployed != start)
    if point['tieNominations']:
        net = sum(cells[nominee][case][0] - cells[start][case][0] for case in validation)
        if net != 0 or not any(cells[nominee][case][0] > cells[start][case][0] for case in validation):
            raise ValueError('The admitted tie must have an actual paired validation win')
    if deployed != start and (deployed != nominee or
            sum(cells[deployed][case][0] - cells[start][case][0] for case in proof) <= 0):
        raise ValueError('The deployed nominee must strictly improve independent qualification')
    return point, trace, grades, audit


def measure_panel(subject, matrix, plan):
    points, vectors, gepa, anchors = prior.measure_panel(subject, matrix, plan)
    cells = {str(index): tuple((int(passed), None, False) for passed in row) for index, row in enumerate(matrix)}
    events = {label: Counter() for label in POLICIES}
    logs = {label: [] for label in POLICIES}
    for seed in plan['seeds']:
        start, roster, cohorts = prior.fixed.archive.transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
        arguments = cells, start, roster, cohorts, seed
        baseline, old, before, _ = early.trial(arguments, 'complete-panel', prior.CAP)
        for label, additional in POLICIES.items():
            point, trace, grades, audit = trial(arguments, additional)
            if old[2] != start and (point, trace, grades) != (baseline, old, before):
                raise ValueError('A strict validation nominee must retain its full path')
            if not point['tieNominations'] and trace[:4] != old[:4]:
                raise ValueError('An extension without a certified tie cannot change the deployment')
            if point['searchLookups'] != baseline['searchLookups'] + audit['tieLookups']:
                raise ValueError('Only paid tie-completion reads may increase search cost')
            points.setdefault(label, Counter()).update({key: point[key] for key in cost.METRICS})
            prior.fixed.fitted.prior.add_vector(vectors.setdefault(label, [0] * len(grades)), grades)
            events[label].update(tieLookups=audit['tieLookups'], tieNominations=point['tieNominations'],
                                 tiePromotions=point['tiePromotions'], extraLookups=point['paidLookups'] - baseline['paidLookups'],
                                 extraPasses=point['holdoutPasses'] - baseline['holdoutPasses'])
            logs[label].append(trace)
    return points, vectors, gepa, anchors, events, {label: digest(trace) for label, trace in logs.items()}


def replay(plan, panels, transfer, receipt):
    totals, subjects, details = {}, {}, {}
    events = {label: Counter() for label in POLICIES}
    for subject, model, matrix in panels:
        name = f'{subject}/{model}'
        points, scores, gepa, anchors, observed, traces = measure_panel(subject, matrix, plan)
        if anchors != transfer['panels'][name]:
            raise ValueError('The audited screen outcomes and independent native traces must reproduce')
        rows = subjects.setdefault(subject, {})
        for label, point in points.items():
            totals.setdefault(label, Counter()).update(point)
            grades = scores[label]
            prior.fixed.fitted.prior.add_vector(rows.setdefault(label, [0] * len(grades)), grades)
        for label, actual in observed.items():
            events[label].update(actual)
        details[name] = {'events': observed, 'traceSha256': traces}
    if (any(totals[label] != point for label, point in transfer['totals'].items())
            or any(totals[label] != point for label, point in receipt['totals'].items())):
        raise ValueError('The recorded fixed and screened controls must reproduce')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('Every holdout score must reconcile to its paired case totals')
    cpo = tuple(f'{prior.fixed.POLICY}/{cap}' for cap in plan['fixedCpoCaps'])
    comparison = frontier.compare(totals, subjects, policies=tuple(POLICIES), draws=plan['bootstrapDraws'],
                                  seed=plan['bootstrapSeed'], groups={'fixed-gepa': gepa,
                                                                      'published-screens': prior.METHODS,
                                                                      'joint': (*cpo, *gepa, *prior.METHODS)})
    joint = comparison[PRIMARY]['joint']
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'passedArchiveGate': joint['holdoutPassDifference'] > 0 and joint['pairedRange95'][0] >= 0,
            'totals': {label: totals[label] for label in (BASELINE, *POLICIES)}, 'events': events,
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
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
