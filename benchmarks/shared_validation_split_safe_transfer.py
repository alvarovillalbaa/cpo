"""Transfer frozen shared-panel CPO against split-safe GEPA at two validation widths."""

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import budgeted_shared_panel_search as frozen
from benchmarks.gepa_disjoint_cases import CaseRows
from cpo._contract import digest


paired, native, gepa = frozen.paired, frozen.native, frozen.gepa
HISTORICAL, FULL, SHARED = 'positional-six', 'split-safe-six', 'split-safe-three'
WIDTHS = {FULL: 6, SHARED: 3}
COHORTS = ('BBH', 'LMentry', 'BBH/seen-task', 'LMentry/seen-task', 'BBH/new-task', 'LMentry/new-task',
           'earlier-screen-cohort', 'disjoint-transfer-cohort')
REFERENCES = {
    'BBH': ('bbh', 'f1d74892f993da121acf101146fd1ae11d8d5de096fa579517df576ea287b196'),
    'LMentry': ('lmentry', 'cb1e9facf188ebc231cd166f70ba50cce75ad4948a48ce6eb24d276b5a99df81'),
    'earlier-screen-cohort': ('earlier-mmlu', '7f64ab4b2798b90d60d6227385d987c157c6ebd36d9fa1c05d63cef3172f27bb'),
    'disjoint-transfer-cohort': ('disjoint-mmlu', '2745bd16e6e023ae0c062c1005bb3e4c9da096a8099e603662dc230bd4515f7e'),
}


def split_loaders(training, validation):
    """Preserve each split's seeded order while giving its rows unique cache IDs."""
    if {row['case'] for row in training} & {row['case'] for row in validation}:
        raise ValueError('GEPA training and validation must have disjoint case IDs')
    return (CaseRows({**row, 'id': i} for i, row in enumerate(training)),
            CaseRows({**row, 'id': i} for i, row in enumerate(validation, len(training))))


@contextmanager
def split_safe_cache():
    module = import_module('gepa.optimize_anything')
    optimize = module.optimize_anything

    def stable(*args, dataset, valset, **kwargs):
        training, validation = split_loaders(dataset, valset)
        return optimize(*args, dataset=training, valset=validation, **kwargs)

    with patch.object(module, 'optimize_anything', stable):
        yield


def validation_width(arguments, width):
    cells, start, roster, (training, validation, qualification, held), seed = arguments
    if width > len(validation):
        raise ValueError('The shortened validation must be an original validation prefix')
    return cells, start, roster, (training, validation[:width], qualification, held), seed


def prepare():
    parent, panels, controls, baseline, historical = frozen.prepare()
    read = paired.frontier.cost.prior.baseline.read_reference
    references = {name: read(f'docs/budgeted-shared-panel-{file}-results-v1.json', sha,
                             {**parent, 'cohort': name})['results']
                  for name, (file, sha) in REFERENCES.items()}
    sources = (Path(__file__), Path(frozen.__file__), Path(gepa.__file__), Path(native.__file__),
               Path(native.native_cost.adapter.math.gepa.__file__),
               paired.reference.ROOT / 'benchmarks/gepa_disjoint_cases.py')
    plan = {**parent, 'protocol': 'shared-validation-split-safe-transfer-v1',
            'parentPlanSha256': digest(parent), 'parentResultSha256': {k: v[1] for k, v in REFERENCES.items()},
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in sources},
            'cohorts': COHORTS, 'policy': frozen.PRIMARY, 'gepaValidationWidths': WIDTHS,
            'scope': 'Preserve wide nonloss CPO and the six-case historical native results for verification. '
                     'Use disjoint GEPA cache IDs on the original six cases and their first three. '
                     'Give both native modes all six proof wrappers and every integer search cap from '
                     'the validation width to 180. Compare with their split-safe subject-tuned union '
                     'at the CPO budget, and directly replay the attaining one-gain schedule for paired '
                     'case resampling. Preserve the original case splits, roster and qualification rule.'}
    return plan, panels, controls, baseline, historical, references


def direct_comparison(panels, plan, schedule, expected, cpo_case_scores):
    paid = {}
    add = paired.frontier.transfer.fitted.prior.add_vector
    for subject, _, matrix in panels:
        cells = {str(index): tuple((int(value), None, False) for value in grades)
                 for index, grades in enumerate(matrix)}
        setting = schedule[subject]
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            if setting == gepa.RETAIN:
                grades = tuple(cells[start][case][0] for case in roles[-1])
                point = {'holdoutPasses': sum(grades), 'paidLookups': 0}
            else:
                group, policy = setting.split(':', 1)
                mode, amount, rule = policy.split('/')
                cap = int(amount)
                arguments = validation_width((cells, start, roster, roles, seed), WIDTHS[group])
                with split_safe_cache():
                    point, _, grades = gepa.native_paths(arguments, mode, cap, cap)[rule][cap]
            paid.setdefault(subject, Counter()).update({key: point[key] for key in native.native_cost.METRICS})
            add(cpo_case_scores[subject].setdefault('selected-gepa', [0] * len(grades)), grades)
    if paid != expected:
        raise ValueError('The corrected attaining schedule must reconcile by subject')
    return frozen.paired_effects.paired_effect(cpo_case_scores, frozen.PRIMARY, 'selected-gepa', plan)


def sweep_native(arguments, low, high, deltas, audit):
    for mode in native.native_cost.MODES:
        legacy = gepa.native_paths(arguments, mode, low, high)
        for rule, paths in legacy.items():
            native.record_boundaries(deltas.setdefault((HISTORICAL, mode, rule), {}), paths, high)
        with split_safe_cache():
            for group, width in WIDTHS.items():
                paths = gepa.native_paths(validation_width(arguments, width), mode, width, high)
                for rule, points in paths.items():
                    native.record_boundaries(deltas.setdefault((group, mode, rule), {}), points, high)
                if group == FULL:
                    for rule in ('paired-gain-1', f'paired-{gepa.frontier.THRESHOLD}'):
                        before, old_trace, _ = legacy[rule][high]
                        after, trace, _ = paths[rule][high]
                        key = f'{mode}/{rule}'
                        audit.setdefault(key, Counter()).update(
                            paths=1, changedNominee=int(old_trace[2] != trace[2]),
                            changedDeployment=int(old_trace[3] != trace[3]),
                            lookupDifference=after['paidLookups'] - before['paidLookups'],
                        )


def measure(panels, plan, controls, baseline, historical, reference):
    stats = {label: Counter() for label in controls.values()}
    subjects, fingerprints, vectors, cache_audit = {}, {}, {}, {}
    low, high, cap = plan['minimumSearchCap'], plan['searchCap'], plan['fullRosterCap']
    add = paired.frontier.transfer.fitted.prior.add_vector
    primary = frozen.PRIMARY
    for subject, model, matrix in panels:
        cells = {str(index): tuple(map(int, row)) for index, row in enumerate(matrix)}
        native_cells = {name: tuple((grade, None, False) for grade in row) for name, row in cells.items()}
        by_subject, deltas = subjects.setdefault(subject, {}), {}
        traces = {label: {policy: [] for policy in (frozen.BASE, primary)} for label in controls.values()}
        for seed in plan['seeds']:
            start, roster, roles = paired.frontier.transfer.archive.transfer.schedule(
                subject, len(matrix[0]), len(matrix), seed, plan,
            )
            by_subject.setdefault(gepa.RETAIN, Counter()).update(
                holdoutPasses=sum(cells[start][case] for case in roles[-1]), paidLookups=0,
            )
            for gain, label in controls.items():
                args = cells, start, roster, roles, seed, cap, gain
                previous, old = frozen.previous.run_trial(frozen.BASE, args)
                original, _, path = paired.reference.point(cells, roles[-1], previous, old)
                traces[label][frozen.BASE].append(path)
                result, paid = frozen.execute_trial(primary, args)
                frozen.audit_trial(cells, start, roles, result, paid, gain, primary)
                current, grades, path = paired.reference.point(cells, roles[-1], result, paid)
                traces[label][primary].append(path)
                stats[label].update(
                    **current, strictCpoPasses=original['holdoutPasses'], strictCpoLookups=original['paidLookups'],
                    nominees=int(result.search.finalist is not None), deployments=int(result.promoted),
                )
                if gain == 1:
                    add(vectors.setdefault(subject, {}).setdefault(primary, [0] * len(grades)), grades)
            sweep_native((native_cells, start, roster, roles, seed), low, high, deltas, cache_audit)
        panel = f'{subject}/{model}'
        fingerprints[panel] = {label: {name: digest(path) for name, path in arms.items()}
                               for label, arms in traces.items()}
        for label, proof in fingerprints[panel].items():
            if proof[frozen.BASE] != baseline['panelPathHashes'][panel][label][frozen.BASE]:
                raise ValueError('Original two-sided CPO paid paths must match')
            if reference is not None and proof[primary] != reference['panelPathHashes'][panel][label][primary]:
                raise ValueError('Frozen shared-panel CPO must reproduce its original paid paths')
        for (group, mode, rule), changes in deltas.items():
            state = Counter()
            for amount in range(WIDTHS.get(group, low), high + 1):
                state.update(changes.get(amount, {}))
                by_subject.setdefault(f'{group}:{mode}/{amount}/{rule}', Counter()).update(state)
    settings = {group: tuple(label for label in next(iter(subjects.values())) if label.startswith(f'{group}:'))
                for group in (HISTORICAL, FULL, SHARED)}
    subject_ceiling = gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    anchors = {label: value['cpo']['paidLookups'] for label, value in historical['comparisons'].items()}
    reproduced = subject_ceiling(subjects, settings[HISTORICAL], anchors)
    for label, result in reproduced.items():
        original_settings = {sub: choice.removeprefix(f'{HISTORICAL}:')
                             for sub, choice in result['settingsBySubject'].items()}
        if {**result, 'settingsBySubject': original_settings} != historical['comparisons'][label]['expandedSubjectCeiling']:
            raise ValueError('The historical native budgets must reproduce before correction')
    budgets = {label: point['paidLookups'] for label, point in stats.items()}
    legacy = subject_ceiling(subjects, settings[HISTORICAL], budgets)
    expanded = subject_ceiling(subjects, (*settings[FULL], *settings[SHARED]), budgets)
    full = subject_ceiling(subjects, settings[FULL], budgets)
    narrow = subject_ceiling(subjects, settings[SHARED], budgets)
    comparisons = {}
    for label, point in stats.items():
        before = baseline['totals'][label][frozen.BASE]
        if (point['strictCpoPasses'], point['strictCpoLookups']) != (before['holdoutPasses'], before['paidLookups']):
            raise ValueError('Strict CPO totals must reconcile to the original archive')
        if reference is not None:
            original = reference['comparisons'][label][primary]
            for field in native.native_cost.METRICS:
                if point[field] != original['cpo'][field] or legacy[label][field] != original['gepa'][field]:
                    raise ValueError('Both original costs and held-out scores must reproduce')
        winner = expanded[label]
        attainment = {sub: rows[winner['settingsBySubject'][sub]] for sub, rows in subjects.items()}
        if any(sum(row[key] for row in attainment.values()) != winner[key] for key in native.native_cost.METRICS):
            raise ValueError('The corrected ceiling must reconcile to its attaining schedule')
        comparisons[label] = {'cpo': point, 'historicalGepa': legacy[label], 'splitSafeSix': full[label],
                              'splitSafeThree': narrow[label], 'splitSafeCombined': winner,
                              'attainingSubjectPoints': attainment}
    one = comparisons[controls[1]]
    one['pairedAgainstAttainingGepa'] = direct_comparison(
        panels, plan, one['splitSafeCombined']['settingsBySubject'], one['attainingSubjectPoints'], vectors,
    )
    if one['pairedAgainstAttainingGepa']['holdoutPassDifference'] != (
        one['cpo']['holdoutPasses'] - one['splitSafeCombined']['holdoutPasses']
    ):
        raise ValueError('Paired held-out vectors must reproduce the corrected margin')
    return {'comparisons': comparisons, 'nativeSettings': {group: len(labels) for group, labels in settings.items()},
            'historicalVsSplitSafeAtMaxCap': cache_audit, 'panelPathHashes': fingerprints,
            'nativeSubjectTotalsSha256': digest(subjects)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    parent, panels, controls, baseline, historical, references = prepare()
    name = args.cohort
    plan = {**parent, 'cohort': name}
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    result = measure(panels[name], plan, controls, baseline[name], historical[name], references.get(name))
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
