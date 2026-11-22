"""Reprice the regression-free qualification gate with exact expected-cost ordering."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import deferred_certificate_no_regression as prior
from cpo._contract import digest
from cpo.regression_free_qualification import run_regression_free_certificate_cycle


cycle, frontier = prior.cycle, prior.frontier
RECEIPT = 'docs/deferred-certificate-no-regression-results-v1.json'
RECEIPT_SHA256 = 'a9d687e06aefa933aeea8d0516903a1bbedd50b7d025297152f86eced49c0203'


def prepare():
    parent, groups, _, _, ceilings, native = prior.prepare()
    read = frontier.cost.prior.baseline.read_reference
    receipt = read(RECEIPT, RECEIPT_SHA256, parent)
    sources = (Path(__file__), Path(prior.__file__), prior.ROOT / 'cpo/regression_free_qualification.py',
               prior.ROOT / 'cpo/expected_qualification.py')
    plan = {**parent, 'protocol': 'regression-free-qualification-replay-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'scope': 'Use the public regression-free certificate cycle on the frozen full-roster trials. '
                     'Verify exact search, nominee and deployment parity with protecting every qualification '
                     'case in the seeded proof. Report saved and added reads and the archived GEPA bounds.'}
    return plan, groups, receipt['results'], ceilings, native


def optimized(incumbent, candidates, validation, qualification_rows, evaluate, *, minimum_gain, **settings):
    if minimum_gain != 1:
        raise ValueError('The regression-free proof requires one gain')
    return run_regression_free_certificate_cycle(
        incumbent, candidates, validation, qualification_rows, evaluate, **settings,
    )


def measure_cohort(panels, plan, receipt, ceilings, native):
    totals, audit, fingerprints = Counter(), Counter(), {}
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        before, after = [], []
        for seed in plan['seeds']:
            start, roster, roles = frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            args = cells, start, roster, roles, seed, plan['fullRosterCap'], 1
            old, old_paid = cycle.execute_path(prior.protect_qualification, *args)
            new, new_paid = cycle.execute_path(optimized, *args)
            if old.search != new.search or old.prompt != new.prompt or old.promoted != new.promoted:
                raise ValueError('The scheduler can change only the independent proof order and price')
            if ([(key, grade) for key, grade in old_paid.items() if key[0] == 'validation']
                    != [(key, grade) for key, grade in new_paid.items() if key[0] == 'validation']):
                raise ValueError('Every validation callback must match the seeded guard')
            seeded, old_grades, old_path = prior.point(cells, roles[-1], old, old_paid)
            actual, new_grades, new_path = prior.point(cells, roles[-1], new, new_paid)
            if old_grades != new_grades:
                raise ValueError('The optimized proof must preserve every held-out grade')
            change = seeded['paidLookups'] - actual['paidLookups']
            totals.update(holdoutPasses=actual['holdoutPasses'], seededLookups=seeded['paidLookups'],
                          optimizedLookups=actual['paidLookups'])
            audit.update(pathsCheaper=int(change > 0), pathsDearer=int(change < 0),
                         grossSavings=max(0, change), grossExtraLookups=max(0, -change))
            before.append(old_path)
            after.append(new_path)
        panel = f'{subject}/{model}'
        if digest(before) != receipt['panelPathHashes'][panel][prior.NO_REGRESSION]:
            raise ValueError('The seeded proof must reproduce every archived callback path')
        fingerprints[panel] = digest(after)
    anchor = receipt['totals'][prior.NO_REGRESSION]
    if totals['holdoutPasses'] != anchor['holdoutPasses'] or totals['seededLookups'] != anchor['paidLookups']:
        raise ValueError('The seeded guard’s original costs and scores must reproduce')
    if (totals['seededLookups'] - totals['optimizedLookups']
            != audit['grossSavings'] - audit['grossExtraLookups']):
        raise ValueError('Every saved or added lookup must reconcile')
    return {'totals': totals, 'audit': audit, 'panelPathHashes': fingerprints,
            'nativeSubjectHindsightBounds': prior.hindsight_bounds(native, ceilings['comparisons'],
                                                                 totals['optimizedLookups'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, receipt, ceilings, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    results = {name: measure_cohort(panels, plan, receipt[name], ceilings[name], native[name])
               for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
