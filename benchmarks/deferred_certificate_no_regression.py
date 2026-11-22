"""Test a one-gain qualification that preserves every incumbent pass."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import deferred_certificate_subject_ceiling as subject_ceiling
from cpo._contract import digest


cycle, frontier = subject_ceiling.cycle, subject_ceiling.frontier
ROOT = cycle.route.ROOT
RECEIPT = 'docs/deferred-certificate-subject-ceiling-results-v1.json'
RECEIPT_SHA256 = '3c92e05d85a303d96393c994610a434ceaf32487fef4437ff1351603235875b9'
RETAIN = cycle.RETAIN
NO_REGRESSION = 'one-gain-without-regressions'


def prepare():
    parent, groups, receipts, controls, _, native = subject_ceiling.prepare()
    read = frontier.cost.prior.baseline.read_reference
    reference = read(RECEIPT, RECEIPT_SHA256, parent)
    paths = (Path(__file__), Path(cycle.__file__), ROOT / 'cpo/deferred_certificate_cycle.py',
             ROOT / 'cpo/paired_qualification.py', ROOT / 'cpo/prechecked_certificate_cycle.py')
    plan = {**parent, 'protocol': 'deferred-certificate-no-regression-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'scope': 'Keep the full-roster CPO search and incumbent precheck for one-gain qualification. '
                     'Require a gain and preserve every qualification pass the incumbent had. '
                     'Use the published one- and two-gain paths as controls. Compare matched paired outcomes '
                     'and price the strongest affordable original GEPA setting from the sealed curves.'}
    return plan, groups, receipts, controls, reference['results'], native


def protect_qualification(incumbent, candidates, validation, qualification_rows, evaluate, *, qualify, **settings):
    return cycle.run_deferred_certificate_cycle(
        incumbent, candidates, validation, (replace(row, critical=True) for row in qualification_rows), evaluate,
        qualify=qualify, **settings,
    )


def point(cells, held, result, paid):
    grades = tuple(cells[result.prompt][case] for case in held)
    path = digest([(*key, passed) for key, passed in paid.items()])
    return {'holdoutPasses': sum(grades), 'paidLookups': len(paid)}, grades, path


def compare_trial(cells, start, roster, roles, seed, cap):
    args = cells, start, roster, roles, seed, cap
    one, one_paid = cycle.execute_path(cycle.run_deferred_certificate_cycle, *args, 1)
    two, two_paid = cycle.execute_path(cycle.run_deferred_certificate_cycle, *args, 2)
    guarded, paid = cycle.execute_path(protect_qualification, *args, 1)

    def selection(ledger):
        return [(key, grade) for key, grade in ledger.items() if key[0] == 'validation']

    if guarded.search != one.search or selection(paid) != selection(one_paid):
        raise ValueError('Protecting independent cases must preserve every validation callback and nominee')
    nominee = one.search.prompt
    deltas = tuple(cells[nominee][case] - cells[start][case] for case in roles[2])
    expected = nominee if 1 in deltas and -1 not in deltas else start
    if guarded.prompt != expected or (guarded.promoted and not one.promoted):
        raise ValueError('The guard must prove one repair with zero regressions on the independent panel')
    if one.promoted:
        decision = 'clean-gain' if guarded.promoted else 'vetoed-regression'
    else:
        decision = 'one-gain-rejection'
    holdout = roles[-1]
    return (point(cells, holdout, one, one_paid), point(cells, holdout, two, two_paid),
            point(cells, holdout, guarded, paid)), decision


def hindsight_bounds(native, prior, budget):
    old = [(native['totals'][label]['paidLookups'], point)
           for label, point in native['subjectTunedGepaHindsight'].items()]
    old.extend((entry['cpo']['paidLookups'], entry['gepa']) for entry in prior.values())
    lower = max([native['totals'][RETAIN]['holdoutPasses'],
                 *(point['holdoutPasses'] for _, point in old if point['paidLookups'] <= budget)])
    upper = min((point['holdoutPasses'] for published_cost, point in old if published_cost >= budget),
                default=None)
    if upper is not None and lower > upper:
        raise ValueError('Archived bounds must preserve monotonic attainable scores')
    return {'lowerPasses': lower, 'upperPasses': upper}


def measure_cohort(panels, plan, receipt, controls, prior, native):
    totals, subjects, fingerprints = {}, {}, {}
    proof_checks = Counter()
    cap = plan['fullRosterCap']
    arms = (controls[1], controls[2], NO_REGRESSION)
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        paths = {label: [] for label in arms}
        rows = subjects.setdefault(subject, {})
        for seed in plan['seeds']:
            start, roster, roles = frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            points, decision = compare_trial(cells, start, roster, roles, seed, cap)
            proof_checks[decision] += 1
            for label, (measured, grades, path) in zip(arms, points, strict=True):
                totals.setdefault(label, Counter()).update(measured)
                frontier.transfer.fitted.prior.add_vector(rows.setdefault(label, [0] * len(grades)), grades)
                paths[label].append(path)
            if decision == 'vetoed-regression':
                delta = points[2][0]['holdoutPasses'] - points[0][0]['holdoutPasses']
                proof_checks.update(passesRecovered=max(0, delta), passesLost=max(0, -delta))
        panel = f'{subject}/{model}'
        fingerprints[panel] = {label: digest(path) for label, path in paths.items()}
        if any(fingerprints[panel][label] != receipt['panelPathHashes'][panel][label]['deferred']
               for label in controls.values()):
            raise ValueError('Every one- and two-gain cost trajectory must match the sealed controls')
    if any(totals[label] != prior[label]['cpo'] for label in controls.values()):
        raise ValueError('Fixed-margin CPO costs and grades must reproduce')
    guard = totals[NO_REGRESSION]
    paired = {label: cycle.route.published.paired_effect(subjects, NO_REGRESSION, label, plan)
              for label in controls.values()}
    if (guard['holdoutPasses'] - totals[controls[1]]['holdoutPasses']
            != proof_checks['passesRecovered'] - proof_checks['passesLost']):
        raise ValueError('Only vetoed promotions can change the one-gain holdout score')
    affordable = {label: point for label, point in native['totals'].items()
                  if (label.startswith('gepa-') or label == RETAIN) and point['paidLookups'] <= guard['paidLookups']}
    fixed = frontier.frontier.highest_scoring(
        {label: point['paidLookups'] for label, point in affordable.items()},
        {label: point['holdoutPasses'] for label, point in affordable.items()}, affordable,
    )
    return {'totals': totals, 'proofChecks': proof_checks, 'pairedAgainstFixedCpo': paired,
            'bestNativeFixed': {'setting': fixed, **affordable[fixed]},
            'nativeSubjectHindsightBounds': hindsight_bounds(native, prior, guard['paidLookups']),
            'panelPathHashes': fingerprints}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, receipts, controls, reference, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    results = {name: measure_cohort(panels, plan, receipts[name], controls, reference[name]['comparisons'], native[name])
               for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}, out,
                  indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
