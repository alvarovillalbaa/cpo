"""Extend an impossible incumbent precheck with two reserved independent cases."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
from itertools import pairwise
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import deferred_two_sided_certificate as previous
from cpo import Row
from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.paired_qualification import QualificationDecision, QualificationObservation
from cpo.single_finalist import FinalistResult


paired, cycle = previous.paired, previous.cycle
gepa = previous.previous.gepa
native_cost = gepa.native_cost
REPORT = 'docs/deferred-two-sided-certificate-results-v1.json'
REPORT_SHA256 = 'b50173bfd6964cceb58ae34f8492fc1df00a70f7c25b1bee6ef46530a26de0c4'
COHORTS = ('earlier-screen-cohort', 'disjoint-transfer-cohort')
EXTENSION = 2


def prepare():
    parent, panels, controls, _, native = previous.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    earlier = read(REPORT, REPORT_SHA256, parent)['results']
    plan = {**parent, 'protocol': 'qualification-precheck-extension-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': REPORT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest()
                             for path in (Path(__file__), Path(gepa.__file__), Path(native_cost.__file__))},
            'cohorts': COHORTS, 'extraCases': EXTENSION,
            'scope': 'Freeze two extra cases outside training, validation, original proof, and final holdout. '
                     'Only activate them when the original incumbent precheck proves the requested gain '
                     'impossible. Reuse the paid prefix and preserve the original required net gain on '
                     'the enlarged panel. Compare two-sided CPO to both native GEPA modes given the same '
                     'extension. Sweep every integer GEPA search cap in the original range. Keep the '
                     'previous six qualification wrappers in the native menu at the same realized lookup budget.'}
    return plan, {cohort: panels[cohort] for cohort in COHORTS}, controls, earlier, native


def reserve_cases(case_count, roles, subject, seed):
    remaining = sorted(set(range(case_count)) - set().union(*roles))
    extra = Random(f'{seed}/{subject}/qualification-precheck-extension').sample(remaining, EXTENSION)
    return roles[0], roles[1], (*roles[2], *extra), roles[3]


def precheck(incumbent, original, extra, minimum, read):
    rows, history = tuple(original), []
    misses, upper = 0, len(rows)
    while len(history) < len(rows):
        row = rows[len(history)]
        passed = read(incumbent, row, 0)
        if type(passed) is not bool:
            raise ValueError('Qualification requires exact boolean outcomes')
        history.append(QualificationObservation(incumbent, row.id, 0, passed))
        upper -= passed
        misses += not passed
        if upper < minimum and extra:
            rows += tuple(extra)
            upper += len(extra)
            extra = ()
        if upper < minimum or misses == minimum:
            break
    return rows, history, misses, upper


def cpo_trial(incumbent, candidates, validation, qualification, evaluate, *, metric_limit, qualify, minimum_gain, seed):
    rows, history, misses, upper = precheck(
        incumbent, qualification[:-EXTENSION], qualification[-EXTENSION:], minimum_gain, qualify,
    )
    if upper < minimum_gain:
        retained = FinalistResult(incumbent, None, 0)
        decision = QualificationDecision('rejected', incumbent, tuple(history), misses - len(rows), upper)
        return FixedPoolCycleResult(retained, decision)
    selection, counts = cycle._screen(incumbent, candidates, validation, evaluate, metric_limit, expected=True)
    if selection.finalist is None:
        decision = QualificationDecision('rejected', incumbent, tuple(history), 0, 0)
    else:
        def read(prompt, row, repeat):
            grade = qualify(prompt, row, repeat)
            if type(grade) is not bool:
                raise ValueError('Qualification requires exact boolean outcomes')
            history.append(QualificationObservation(prompt, row.id, repeat, grade))
            return grade

        decision = paired.ordered._finish_with_partner_evidence(
            incumbent, selection.prompt, rows, read, history, counts, minimum_gain, seed,
        )
    return FixedPoolCycleResult(selection, decision)


def native_trial(arguments, mode, cap, *, gain):
    cells, start, roster, (train, validation, qualification, held), seed = arguments
    rows = tuple(Row(str(case), 'qualification') for case in qualification)
    proof, search = {}, {}
    nominee = deployed = start

    def qualify(prompt, row, repeat):
        key = prompt, row.id
        if repeat or key in proof or row not in rows or prompt not in (start, nominee):
            raise ValueError('The native qualification must pay each independent reply once')
        proof[key] = bool(cells[prompt][int(row.id)][0])
        return proof[key]

    def observe(prompt, case):
        if prompt not in (start, *roster) or case not in (*train, *validation):
            raise ValueError('Native search left its sealed roster or cases')
        key = prompt, case
        if key not in search:
            if len(search) >= cap:
                raise ValueError('Native search exceeded its paid cap')
            search[key] = bool(cells[prompt][case][0])
        return search[key]

    active, history, _, upper = precheck(start, rows[:-EXTENSION], rows[-EXTENSION:], gain, qualify)
    if upper >= gain:
        math = native_cost.adapter.math
        nominee, _ = math.gepa.optimize_by_paid_reads(
            start, roster, train, validation, observe, lambda: len(search),
            paid_limit=cap, batched=math.GEPA[mode.removesuffix('-precheck')], seed=seed,
        )
        if nominee != start:
            validation_grades = ([passed for (prompt, case), passed in search.items()
                                  if prompt == name and case in validation] for name in (start, nominee))
            counts = tuple((sum(grades), len(grades)) for grades in validation_grades)

            def read(prompt, row, repeat):
                grade = qualify(prompt, row, repeat)
                history.append(QualificationObservation(prompt, row.id, repeat, grade))
                return grade

            deployed = paired.ordered._finish_with_partner_evidence(
                start, nominee, active, read, history, counts, gain, seed,
            ).prompt
    net = sum(cells[nominee][int(row.id)][0] - cells[start][int(row.id)][0] for row in active)
    if deployed != (nominee if net >= gain else start) or len(proof) > 2 * len(active):
        raise ValueError('Native deployment must reconcile to the exact independent qualification')
    grades = tuple(cells[deployed][case][0] for case in held)
    point = {'holdoutPasses': sum(grades), 'paidLookups': len(search) + len(proof),
             'searchLookups': len(search), 'qualificationLookups': len(proof)}
    return point, (seed, start, nominee, deployed, len(active)), grades


def native_sweep(original, extended, low, high, controls):
    engine = native_cost.adapter.math.gepa
    cells, start, _, roles, _ = original
    missed = sum(not cells[start][case][0] for case in roles[2])
    with patch.object(engine, 'optimize_by_paid_reads', gepa.subject_ceiling.reuse_native_search(
            engine.optimize_by_paid_reads)):
        for mode in native_cost.MODES:
            before = gepa.native_paths(original, mode, low, high)
            for rule, paths in before.items():
                yield mode, rule, paths
            for gain in controls:
                with patch.object(native_cost, 'run', partial(native_trial, gain=gain)):
                    paths = native_cost.budget_paths(extended, mode, low, high)
                if missed >= gain:
                    anchor = before['paired-gain-1' if gain == 1 else f'paired-{gepa.frontier.THRESHOLD}']
                    if anchor.keys() != paths.keys() or any(
                        any(value != anchor[cap][0][key] for key, value in point.items())
                        or trace[:4] != anchor[cap][1][:4] or grades != anchor[cap][2]
                        for cap, (point, trace, grades) in paths.items()
                    ):
                        raise ValueError('An inactive extension must preserve the matching native path')
                yield mode, f'paired-extension-gain-{gain}', paths


def record_boundaries(target, paths, high):
    for lower, upper in pairwise((*paths, high + 1)):
        point, _, grades = paths[lower]
        if (point['searchLookups'] > lower or point['holdoutPasses'] != sum(grades)
                or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
            raise ValueError('A native path must reconcile its paid caps and scores')
        measured = {key: point[key] for key in native_cost.METRICS}
        target.setdefault(lower, Counter()).update(measured)
        target.setdefault(upper, Counter()).subtract(measured)


def measure(panels, plan, controls, earlier, native):
    subjects, totals, fingerprints = {}, {}, {}
    stats = {label: Counter() for label in controls.values()}
    low, high, cap = plan['minimumSearchCap'], plan['searchCap'], plan['fullRosterCap']
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        native_cells = {name: tuple((grade, None, False) for grade in row) for name, row in cells.items()}
        by_subject = subjects.setdefault(subject, {})
        traces, deltas = {label: [] for label in controls.values()}, {}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            extended = reserve_cases(len(matrix[0]), roles, subject, seed)
            by_subject.setdefault(gepa.RETAIN, Counter()).update(
                holdoutPasses=sum(cells[start][case] for case in roles[-1]), paidLookups=0,
            )
            for gain, label in controls.items():
                before, old = previous.run_trial(previous.EXPECTED, (cells, start, roster, roles, seed, cap, gain))
                after, paid = paired.cycle.execute_path(cpo_trial, cells, start, roster, extended, seed, cap, gain)
                original, _, trace = paired.reference.point(cells, roles[-1], before, old)
                traces[label].append(trace)
                result, _, _ = paired.reference.point(cells, roles[-1], after, paid)
                opened = len(roles[2]) - sum(cells[start][case] for case in roles[2]) < gain
                if not opened and (before != after or list(old.items()) != list(paid.items())):
                    raise ValueError('An inactive extension must preserve the complete CPO path')
                active = extended[2] if opened else roles[2]
                previous.previous.check_deployment(cells, start, (*roles[:2], active, roles[-1]), after, gain)
                if after.qualification_evaluations > 2 * len(active):
                    raise ValueError('The CPO proof exceeded the active qualification allowance')
                stats[label].update(
                    **result, baselineLookups=original['paidLookups'], baselinePasses=original['holdoutPasses'],
                    opened=int(opened), newNominees=int(opened and after.search.finalist is not None),
                    newPromotions=int(opened and after.promoted),
                )
            original, widened = ((native_cells, start, roster, cases, seed) for cases in (roles, extended))
            for mode, rule, paths in native_sweep(original, widened, low, high, controls):
                record_boundaries(deltas.setdefault((mode, rule), {}), paths, high)
        name = f'{subject}/{model}'
        fingerprints[name] = {label: digest(trace) for label, trace in traces.items()}
        if any(fingerprint != earlier['panelPathHashes'][name][label][previous.EXPECTED]
               for label, fingerprint in fingerprints[name].items()):
            raise ValueError('Every original two-sided callback path must reproduce')
        for (mode, rule), changes in deltas.items():
            state = Counter()
            for budget in range(low, high + 1):
                state.update(changes.get(budget, {}))
                label = f'{mode}/{budget}/{rule}'
                totals.setdefault(label, Counter()).update(state)
                by_subject.setdefault(label, Counter()).update(state)
    originals = tuple(label for label in totals if '/paired-extension-' not in label)
    extended = tuple(label for label in totals if '/paired-extension-' in label)
    subject_ceiling = gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    published_budgets = {label: row['cpo']['paidLookups'] for label, row in native['comparisons'].items()}
    original_anchors = subject_ceiling(subjects, originals, published_budgets)
    if original_anchors != {label: row['expandedSubjectCeiling'] for label, row in native['comparisons'].items()}:
        raise ValueError('The complete original native menu must reproduce both published subject ceilings')
    budgets = {label: point['paidLookups'] for label, point in stats.items()}
    previous_only = subject_ceiling(subjects, originals, budgets)
    union = subject_ceiling(subjects, (*originals, *extended), budgets)
    comparisons = {}
    for gain, label in controls.items():
        point = stats[label]
        expected = earlier['totals'][label][previous.EXPECTED]
        if point['baselineLookups'] != expected['paidLookups'] or point['baselinePasses'] != expected['holdoutPasses']:
            raise ValueError('The original CPO score and cost must reproduce')
        matched = tuple(setting for setting in extended if setting.endswith(f'gain-{gain}'))
        equal_gate = subject_ceiling(subjects, matched, {label: budgets[label]})[label]
        best = union[label]
        attaining = {name: subject[best['settingsBySubject'][name]] for name, subject in subjects.items()}
        if any(sum(row[key] for row in attaining.values()) != best[key] for key in native_cost.METRICS):
            raise ValueError('The chosen native schedule must attain its subject-tuned total')
        comparisons[label] = {
            'cpo': point, 'originalMenu': previous_only[label], 'expandedMenu': best, 'matchedGate': equal_gate,
            'attainingSubjectPoints': attaining,
        }
    return {'comparisons': comparisons, 'originalSettings': len(originals), 'extensionSettings': len(extended),
            'originalPanelPathHashes': fingerprints, 'nativeSubjectTotalsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    parent, panels, controls, earlier, native = prepare()
    plan = {**parent, 'cohort': args.cohort}
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    name = args.cohort
    result = measure(panels[name], plan, controls, earlier[name], native[name])
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
