"""Compare broader and deeper shared validation under the same paid cap."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import deferred_two_sided_certificate as previous
from benchmarks import qualification_precheck_extension as native
from benchmarks import recorded_sequential_certificate_screen as paired_effects
from cpo._contract import digest
from cpo.shared_validation_cycle import SCHEDULES, run_shared_validation_cycle


paired, cycle, gepa = previous.paired, previous.cycle, native.gepa
REPORT = 'docs/deferred-two-sided-certificate-results-v1.json'
REPORT_SHA256 = 'b50173bfd6964cceb58ae34f8492fc1df00a70f7c25b1bee6ef46530a26de0c4'
COHORTS = ('BBH', 'LMentry', 'earlier-screen-cohort', 'disjoint-transfer-cohort')
METHODS = {f'{name}/{margin}': (name, gain)
           for name in SCHEDULES for margin, gain in (('nonloss', 0), ('gain', 1))}
BASE = previous.EXPECTED
PRIMARY = 'wide/nonloss'


def prepare():
    parent, panels, controls, _, native_reference = previous.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    earlier = read(REPORT, REPORT_SHA256, parent)['results']
    sources = (Path(__file__), Path(cycle.__file__), Path(native.__file__), Path(gepa.__file__),
               Path(paired_effects.__file__), paired.reference.ROOT / 'cpo/shared_validation_cycle.py')
    plan = {**parent, 'protocol': 'budgeted-shared-panel-search-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REPORT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'cohorts': COHORTS, 'policies': METHODS,
            'scope': 'Use the original independent precheck and qualification. Spend the same cap on '
                     'shared validation rounds that narrow eight candidates over three cases or four '
                     'candidates over five cases. Rank by the paid score on common cases, with seeded '
                     'order breaking ties. Compare nomination at observed nonloss and observed gain. '
                     'Keep strict validation on critical panels and compare the four policies to the '
                     'full seeded native GEPA menu at realized cost. Replay the native schedule attaining '
                     'the wide nonloss ceiling at one qualification gain and resample the paired case differences.'}
    return plan, panels, controls, earlier, native_reference


def execute_trial(method, args):
    schedule, margin = METHODS[method]
    runner = partial(run_shared_validation_cycle, schedule=schedule, validation_gain=margin)
    return paired.cycle.execute_path(runner, *args)


def audit_trial(cells, start, roles, result, ledger, proof_gain, method):
    _, margin = METHODS[method]
    nominee = result.search.finalist
    if nominee is None:
        return 0
    observed = {prompt: {case: grade for (role, name, case), grade in ledger.items()
                         if role == 'validation' and name == prompt}
                for prompt in (start, nominee)}
    base, contender = observed[start], observed[nominee]
    if not base or base.keys() != contender.keys() or sum(contender.values()) - sum(base.values()) < margin:
        raise ValueError('Every nominee needs the stated margin on its same paid validation cases')
    qualified = sum(cells[nominee][case] - cells[start][case] for case in roles[2]) >= proof_gain
    if result.prompt != (nominee if qualified else start):
        raise ValueError('The original exact independent qualification must determine deployment')
    return len(base)


def paired_against_attaining_schedule(panels, plan, attained, outcomes):
    target = 'attaining-gepa'
    schedule = attained['gepa']['settingsBySubject']
    totals = {}
    add = paired.frontier.transfer.fitted.prior.add_vector
    for subject, _, matrix in panels:
        cells = {str(index): tuple((int(grade), None, False) for grade in row) for index, row in enumerate(matrix)}
        setting = schedule[subject]
        cost = totals.setdefault(subject, Counter())
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            if setting == gepa.RETAIN:
                grades = tuple(cells[start][case][0] for case in roles[-1])
                point = {'holdoutPasses': sum(grades), 'paidLookups': 0}
            else:
                mode, amount, rule = setting.split('/')
                cap = int(amount)
                point, _, grades = gepa.native_paths((cells, start, roster, roles, seed), mode, cap, cap)[rule][cap]
            cost.update({field: point[field] for field in native.native_cost.METRICS})
            add(outcomes[subject].setdefault(target, [0] * len(grades)), grades)
    if totals != attained['attainingSubjectPoints']:
        raise ValueError('A direct native replay must reproduce every attaining subject cost and score')
    comparison = paired_effects.paired_effect(outcomes, PRIMARY, target, plan)
    if comparison['holdoutPassDifference'] != attained['cpo']['holdoutPasses'] - attained['gepa']['holdoutPasses']:
        raise ValueError('The paired native case vectors must attain the same score')
    return comparison


def measure(panels, plan, controls, earlier, native_reference):
    stats = {label: {method: Counter() for method in METHODS} for label in controls.values()}
    subjects, outcomes, fingerprints = {}, {}, {}
    low, high, cap = plan['minimumSearchCap'], plan['searchCap'], plan['fullRosterCap']
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        native_cells = {name: tuple((grade, None, False) for grade in row) for name, row in cells.items()}
        subject_native = subjects.setdefault(subject, {})
        traces = {label: {method: [] for method in (BASE, *METHODS)} for label in controls.values()}
        deltas = {}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            subject_native.setdefault(gepa.RETAIN, Counter()).update(
                holdoutPasses=sum(cells[start][case] for case in roles[-1]), paidLookups=0,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, cap, gain
                original, old = previous.run_trial(BASE, args)
                anchor, anchor_grades, path = paired.reference.point(cells, roles[-1], original, old)
                traces[label][BASE].append(path)
                subject_grades = outcomes.setdefault(label, {}).setdefault(subject, {})
                add = paired.frontier.transfer.fitted.prior.add_vector
                add(subject_grades.setdefault(BASE, [0] * len(anchor_grades)), anchor_grades)
                for method in METHODS:
                    result, paid = execute_trial(method, args)
                    measured = audit_trial(cells, start, roles, result, paid, gain, method)
                    if not original.search.evaluations and original.search.finalist is None:
                        if original != result or list(old.items()) != list(paid.items()):
                            raise ValueError('A closed qualification precheck must preserve the entire path')
                    point, grades, path = paired.reference.point(cells, roles[-1], result, paid)
                    stats[label][method].update(
                        **point, changedNominees=int(result.search.finalist != original.search.finalist),
                        changedDeployments=int(result.prompt != original.prompt),
                        nominationCases=measured, nominated=int(bool(measured)), promoted=int(result.promoted),
                        passDifference=point['holdoutPasses'] - anchor['holdoutPasses'],
                        lookupDifference=point['paidLookups'] - anchor['paidLookups'],
                    )
                    add(subject_grades.setdefault(method, [0] * len(grades)), grades)
                    traces[label][method].append(path)
            arguments = native_cells, start, roster, roles, seed
            for mode in native.native_cost.MODES:
                for rule, paths in gepa.native_paths(arguments, mode, low, high).items():
                    native.record_boundaries(deltas.setdefault((mode, rule), {}), paths, high)
        panel = f'{subject}/{model}'
        fingerprints[panel] = {label: {method: digest(path) for method, path in methods.items()}
                               for label, methods in traces.items()}
        if any(trace[BASE] != earlier['panelPathHashes'][panel][label][BASE]
               for label, trace in fingerprints[panel].items()):
            raise ValueError('Every baseline path must match its published trace')
        for (mode, rule), changes in deltas.items():
            point = Counter()
            for budget in range(low, high + 1):
                point.update(changes.get(budget, {}))
                subject_native.setdefault(f'{mode}/{budget}/{rule}', Counter()).update(point)
    settings = tuple(label for label in next(iter(subjects.values())) if label != gepa.RETAIN)
    subject_ceiling = gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    anchors = {label: row['cpo']['paidLookups'] for label, row in native_reference['comparisons'].items()}
    if subject_ceiling(subjects, settings, anchors) != {
        label: row['expandedSubjectCeiling'] for label, row in native_reference['comparisons'].items()
    }:
        raise ValueError('Both published subject-tuned native budgets must reproduce')
    budgets = {f'{label}/{method}': row['paidLookups'] for label, methods in stats.items()
               for method, row in methods.items()}
    native_points = subject_ceiling(subjects, settings, budgets)
    for label, methods in stats.items():
        baseline = earlier['totals'][label][BASE]
        for method, point in methods.items():
            if (point['paidLookups'] - point['lookupDifference'] != baseline['paidLookups']
                    or point['holdoutPasses'] - point['passDifference'] != baseline['holdoutPasses']):
                raise ValueError('Paid and score differences must reconcile to the published baseline')
            comparator = native_points[f'{label}/{method}']
            paired_change = paired_effects.paired_effect(outcomes[label], method, BASE, plan)
            if paired_change['holdoutPassDifference'] != point['passDifference']:
                raise ValueError('The paired held-out vectors must reconcile to actual scores')
            attaining = {subject: rows[comparator['settingsBySubject'][subject]]
                         for subject, rows in subjects.items()}
            if any(sum(row[key] for row in attaining.values()) != comparator[key]
                   for key in native.native_cost.METRICS):
                raise ValueError('The selected GEPA schedule must attain the reported ceiling')
            methods[method] = {'cpo': point, 'gepa': comparator, 'pairedAgainstBaseline': paired_change,
                               'attainingSubjectPoints': attaining}
    one = controls[1]
    primary = stats[one][PRIMARY]
    primary['pairedAgainstAttainingGepa'] = paired_against_attaining_schedule(panels, plan, primary, outcomes[one])
    return {'comparisons': stats, 'panelPathHashes': fingerprints, 'nativeSettings': len(settings),
            'nativeSubjectTotalsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    parent, panels, controls, earlier, native_reference = prepare()
    cohort = args.cohort
    plan = {**parent, 'cohort': cohort}
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    result = measure(panels[cohort], plan, controls, earlier[cohort], native_reference[cohort])
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
