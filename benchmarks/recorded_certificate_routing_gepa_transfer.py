"""Compare certificate screening on separate archived checkpoints at matched GEPA costs."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import recorded_certificate_budget_route as routes
from benchmarks import recorded_shortlist_model_transfer as anchor
from cpo._contract import digest


frontier = routes.frontier
RETAIN = routes.RETAIN
RECEIPT = 'docs/recorded-certificate-budget-route-results-v1.json'
RECEIPT_SHA256 = '7c3990f0d153fe1c8cf451bc642a9447ad9c1d2d05bbeb5be0c3e046ea453878'
ANCHOR = 'docs/recorded-shortlist-model-transfer-results-v1.json'
ANCHOR_SHA256 = 'db9cc74e9577af343509cb9b0bc0b8fe99e88cab49991c05a1965d984bcf52b9'


def prepare():
    prior, groups, _, _ = routes.prepare()
    read = frontier.cost.prior.baseline.read_reference
    receipt = read(RECEIPT, RECEIPT_SHA256, prior)
    archived, _, _, _ = anchor.prepare()
    reference = read(ANCHOR, ANCHOR_SHA256, archived)
    settings = ('gepaVersion', 'seeds', 'challengers', 'caseCounts', 'searchCap', 'minimumSearchCap')
    if (any(prior[key] != archived[key] for key in settings)
            or anchor.transfer.schedule is not frontier.transfer.archive.transfer.schedule
            or anchor.cost is not frontier.cost):
        raise ValueError('The transfer must preserve native search, case assignments and candidate rosters')
    targets = {name: panels for name, panels in groups.items() if name in prior['targetPanels']}
    baseline = {}
    for name, panels in targets.items():
        family, scope = name.split('/')
        key = anchor.KNOWN_TASKS if scope == 'seen-task' else anchor.NEW_TASKS
        expected = reference['results'][key][family]
        if set(expected['panelsAtOriginalCap']) != {f'{subject}/{model}' for subject, model, _ in panels}:
            raise ValueError('The native reference must cover the same model panels')
        baseline[name] = expected['totals']
    paths = (Path(__file__), Path(frontier.__file__), Path(anchor.__file__))
    plan = {**prior, 'protocol': 'recorded-certificate-routing-gepa-transfer-v1',
            'parentPlanSha256': digest(prior), 'parentReceiptSha256': RECEIPT_SHA256,
            'nativeAnchorPlanSha256': digest(archived), 'nativeAnchorReceiptSha256': ANCHOR_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'scope': 'Compare all six CPO settings with sequential and batched GEPA at caps 6 through 180 '
                     'under both published qualification margins and the matched two-gain precheck. '
                     'Verify the historical one-gain GEPA curves. Reselect the strongest affordable '
                     'native setting or retained starts on each paired case draw and report subject '
                     'hindsight at each observed CPO budget.'}
    return plan, targets, receipt['results'], baseline


def distinct_controls(controls, totals, subjects):
    """Retain the cheapest representative of each exact paired case vector."""
    representatives = {}
    for label in sorted(controls, key=lambda label: (totals[label]['paidLookups'], label)):
        grades = tuple(tuple(rows[label]) for _, rows in sorted(subjects.items()))
        representatives.setdefault(grades, label)
    return tuple(representatives.values())


def compare_cohort(panels, plan, receipt, anchor_totals):
    totals, subjects, prices = {}, {}, {}
    audit = Counter()
    add = frontier.transfer.fitted.prior.add_vector
    for subject, model, matrix in panels:
        panel = f'{subject}/{model}'
        points, scores, _, _ = routes.measure_panel(subject, matrix, plan, receipt['panelPathHashes'][panel])
        control_paths = {label: receipt['panelPathHashes'][panel][label] for label in frontier.POLICIES.values()}
        native, native_scores, checked = frontier.measure_panel(subject, matrix, plan, control_paths)
        for label, point in points.items():
            if label in native and (native[label] != point or native_scores[label] != scores[label]):
                raise ValueError('The native and CPO replay must share retained starts and exact case vectors')
        audit.update(checked)
        rows = subjects.setdefault(subject, {})
        subject_totals = prices.setdefault(subject, {})
        for label, point in {**native, **points}.items():
            totals.setdefault(label, Counter()).update(point)
            subject_totals.setdefault(label, Counter()).update(point)
            grades = scores[label] if label in scores else native_scores[label]
            add(rows.setdefault(label, [0] * len(grades)), grades)
    if any(totals[label] != point for label, point in receipt['totals'].items()):
        raise ValueError('All six CPO results and retained starts must reproduce')
    if any(totals[f'{label}/gain-1'] != point for label, point in anchor_totals.items()
           if label.startswith('gepa-')):
        raise ValueError('The original native one-gain curves must match all published paid points')
    if any(sum(sum(rows[label]) for rows in subjects.values()) != point['holdoutPasses']
           for label, point in totals.items()):
        raise ValueError('The matched comparison must account for all held-out grades')

    policies = tuple(label for label in receipt['totals'] if label != RETAIN)
    controls = tuple(label for label in totals if label not in (*policies, RETAIN))
    distinct = distinct_controls(controls, totals, subjects)
    paired = frontier.frontier.compare(totals, subjects, policies=policies, draws=plan['bootstrapDraws'],
                                       seed=plan['bootstrapSeed'], groups={'any-native-wrapper': distinct})
    ceilings = frontier.transfer.fitted.prior.by_subject_ceiling(
        prices, controls, {label: totals[label]['paidLookups'] for label in policies},
    )
    return {'totals': totals, 'comparisons': {label: row['any-native-wrapper'] for label, row in paired.items()},
            'subjectTunedGepaHindsight': ceilings, 'nativeSettings': len(controls),
            'distinctNativeCaseVectors': len(distinct), 'caseVectorsSha256': digest(subjects), **audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, receipt, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: compare_cohort(panels, plan, receipt[name], reference[name]) for name, panels in groups.items()}
    with args.out.open('x') as destination:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results},
                  destination, indent=2, sort_keys=True)
        destination.write('\n')


if __name__ == '__main__':
    main()
