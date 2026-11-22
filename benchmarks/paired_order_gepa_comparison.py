"""Compare paired-order CPO with native GEPA given the same qualification order."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import deferred_certificate_paired_order as paired
from benchmarks import deferred_certificate_subject_ceiling as subject_ceiling
from cpo._contract import digest
from cpo.paired_qualification import QualificationObservation


cycle, frontier, native_cost = subject_ceiling.cycle, subject_ceiling.frontier, subject_ceiling.native_cost
RETAIN = subject_ceiling.RETAIN
ORDER_REPORT = 'docs/deferred-certificate-paired-order-results-v1.json'
ORDER_SHA256 = 'd3b7875a8c6ab6a42add7eea10314870150fbc661df8c7c2161d5e117db9801e'
CEILING_REPORT = 'docs/deferred-certificate-subject-ceiling-results-v1.json'
CEILING_SHA256 = '3c92e05d85a303d96393c994610a434ceaf32487fef4437ff1351603235875b9'
RULES = ('gain-1', 'gain-2', frontier.THRESHOLD)


def prepare():
    parent, groups, _, policies, _, native = subject_ceiling.prepare()
    paired_plan, *_ = paired.prepare()
    read = native_cost.prior.baseline.read_reference
    ordered_receipt = read(ORDER_REPORT, ORDER_SHA256, paired_plan)
    ceiling_receipt = read(CEILING_REPORT, CEILING_SHA256, parent)
    sources = (Path(__file__), Path(subject_ceiling.__file__), Path(frontier.__file__),
               Path(native_cost.adapter.__file__), Path(paired.ordered.__file__))
    plan = {**parent, 'protocol': 'paired-order-gepa-comparison-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': CEILING_SHA256,
            'pairedPlanSha256': digest(paired_plan), 'pairedReceiptSha256': ORDER_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'scope': 'Keep all three original native GEPA qualification wrappers and add a same-case order '
                     'to each. Require exact search, nomination, deployment and score parity. Compare '
                     'paired-order CPO at its actual budgets with both original and expanded GEPA menus, '
                     'including the strongest common setting and exact subject-tuned hindsight.'}
    return plan, groups, policies, ordered_receipt['results'], ceiling_receipt['results'], native


def native_paired_proof(minimum):
    def qualify(incumbent, nominee, rows, observe, prefix, counts, seed, mode):
        if mode != native_cost.adapter.EXPECTED or tuple(prefix) != tuple(row.id for row in rows[:len(prefix)]):
            raise ValueError('The native paired proof needs its paid incumbent prefix and expected-cost wrapper')
        if any(type(passed) is not bool for passed in prefix.values()):
            raise ValueError('The paid incumbent prefix must contain boolean grades')
        history = [QualificationObservation(incumbent, case, 0, grade) for case, grade in prefix.items()]

        def read(prompt, row, repeat):
            grade = observe(prompt, row, repeat)
            if type(grade) is not bool:
                raise ValueError('Qualification requires exact boolean outcomes')
            history.append(QualificationObservation(prompt, row.id, repeat, grade))
            return grade

        return paired.ordered._finish_with_partner_evidence(
            incumbent, nominee, rows, read, history, counts, minimum, seed,
        )
    return qualify


def native_paths(arguments, mode, low, high):
    engine = native_cost.adapter.math.gepa
    paired_two = native_paired_proof(2)
    with patch.object(engine, 'optimize_by_paid_reads', subject_ceiling.reuse_native_search(engine.optimize_by_paid_reads)):
        one, two = frontier.matched.native_paths(arguments, mode, low, high)
        with patch.object(native_cost, 'run', frontier.gepa_threshold):
            threshold = native_cost.budget_paths(arguments, mode, low, high)
        with patch.object(native_cost.adapter, 'qualify_with_prefix', native_paired_proof(1)):
            ordered_one = native_cost.budget_paths(arguments, mode, low, high)
        with patch.object(native_cost.adapter, 'qualify_with_prefix', paired_two):
            ordered_two = native_cost.budget_paths(arguments, mode, low, high)
        with (patch.object(native_cost, 'run', frontier.gepa_threshold),
              patch.object(frontier.prior, 'minimum_two', paired_two)):
            ordered_threshold = native_cost.budget_paths(arguments, mode, low, high)

    paths = {}
    for label, original, ordered in zip(RULES, (one, two, threshold),
                                        (ordered_one, ordered_two, ordered_threshold), strict=True):
        if original.keys() != ordered.keys():
            raise ValueError('Paired ordering cannot change any native search boundary')
        for cap, (before, trace, grades) in original.items():
            after, reordered, new_grades = ordered[cap]
            if (trace[:4] != reordered[:4] or grades != new_grades
                    or before['searchLookups'] != after['searchLookups']):
                raise ValueError('Paired ordering cannot change native search charges, nominees, or deployments')
        paths[label] = original
        paths[f'paired-{label}'] = ordered
    return paths


def best_fixed(totals, settings, budget):
    affordable = {label: totals[label] for label in (*settings, RETAIN) if totals[label]['paidLookups'] <= budget}
    selected = frontier.frontier.highest_scoring(
        {label: point['paidLookups'] for label, point in affordable.items()},
        {label: point['holdoutPasses'] for label, point in affordable.items()}, affordable,
    )
    return {'setting': selected, **affordable[selected]}


def measure_cohort(panels, plan, policies, ordered, prior, native):
    totals, subjects, audit = {}, {}, Counter()
    with (patch.object(subject_ceiling, 'native_paths', native_paths),
          patch.object(cycle, 'run_deferred_certificate_cycle', paired.ordered.run_paired_order_certificate_cycle)):
        for subject, model, matrix in panels:
            receipt = {label: {'deferred': fingerprint}
                       for label, fingerprint in ordered['panelPathHashes'][f'{subject}/{model}'].items()}
            panel, checked = subject_ceiling.measure_panel(subject, matrix, plan, receipt, policies)
            audit.update(checked)
            rows = subjects.setdefault(subject, {})
            for label, point in panel.items():
                totals.setdefault(label, Counter()).update(point)
                rows.setdefault(label, Counter()).update(point)
    original = {label: point for label, point in native['totals'].items() if label.startswith('gepa-')}
    if any(totals[label] != point for label, point in original.items()) or totals[RETAIN] != native['totals'][RETAIN]:
        raise ValueError('Every original native setting and retained start must reproduce')
    paired_controls = tuple(label for label in totals if label.startswith('gepa-') and '/paired-' in label)
    if len(paired_controls) != len(original):
        raise ValueError('Each original GEPA setting needs an otherwise identical paired control')
    changes = Counter()
    for label in original:
        prefix, rule = label.rsplit('/', 1)
        before, after = totals[label], totals[f'{prefix}/paired-{rule}']
        if before['holdoutPasses'] != after['holdoutPasses']:
            raise ValueError('Every paired control must preserve its archived grades')
        saved = before['paidLookups'] - after['paidLookups']
        changes.update(cheaperSettings=int(saved > 0), dearerSettings=int(saved < 0), equalSettings=int(saved == 0))
    for label in policies.values():
        point = ordered['totals'][label]
        if totals[label] != {'paidLookups': point['pairedLookups'], 'holdoutPasses': point['holdoutPasses']}:
            raise ValueError('The paired CPO costs and grades must reproduce')

    ceiling = frontier.transfer.fitted.prior.by_subject_ceiling
    original_budgets = {label: row['cpo']['paidLookups'] for label, row in prior['comparisons'].items()}
    if ceiling(subjects, tuple(original), original_budgets) != {
        label: row['gepa'] for label, row in prior['comparisons'].items()
    }:
        raise ValueError('The earlier subject-tuned schedules must reproduce at their original budgets')
    budgets = {label: totals[label]['paidLookups'] for label in policies.values()}
    original_ceilings = ceiling(subjects, tuple(original), budgets)
    expanded = (*original, *paired_controls)
    new_ceilings = ceiling(subjects, expanded, budgets)
    comparisons = {}
    for label, winner in new_ceilings.items():
        fixed = best_fixed(totals, expanded, budgets[label])
        if winner['holdoutPasses'] < max(fixed['holdoutPasses'], original_ceilings[label]['holdoutPasses']):
            raise ValueError('A larger control menu cannot reduce the attainable score')
        subject_points = {subject: rows[winner['settingsBySubject'][subject]] for subject, rows in subjects.items()}
        if (winner['paidLookups'] > budgets[label]
                or any(sum(point[key] for point in subject_points.values()) != winner[key]
                       for key in native_cost.METRICS)):
            raise ValueError('The attaining subject schedule must account for every pass and lookup within budget')
        comparisons[label] = {
            'cpo': totals[label], 'bestOriginalFixed': best_fixed(totals, tuple(original), budgets[label]),
            'bestExpandedFixed': fixed, 'originalSubjectCeiling': original_ceilings[label],
            'expandedSubjectCeiling': winner,
            'holdoutPassDifference': totals[label]['holdoutPasses'] - winner['holdoutPasses'],
            'attainingSubjectPoints': subject_points,
        }
    return {'comparisons': comparisons, 'nativeSettings': len(expanded), 'nativeCostChanges': changes,
            'wrappedPaths': audit, 'subjectTotalsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, policies, ordered, earlier, native = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    results = {name: measure_cohort(panels, plan, policies, ordered[name], earlier[name], native[name])
               for name, panels in groups.items()}
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}, out,
                  indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
