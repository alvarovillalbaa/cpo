"""Calibrate a CPO schedule on one model and audit it on another."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import quoted_schedule_discovery_transfer as discovery
from cpo._contract import digest
from cpo.two_sided_certificate_cycle import _run


parent = discovery.parent
adaptive, controls, native, transfer = discovery.adaptive, discovery.controls, discovery.native, discovery.transfer
continuous, RETAIN, ROUTED = parent.continuous, parent.RETAIN, parent.ROUTED
FIT = 'docs/quoted-schedule-discovery-fit-v1.json'
FIT_SHA = '45688d23c802768297763ccd91786952ccc4420c01e076ddaddd4577f84007cf'
QUOTED, EAGER, GEPA, PREFIX = 'task-quoted', 'task-eager', 'task-gepa', 'frozen-prefix'


def split_cases(subject, held):
    ordered = sorted(held, key=lambda case: digest(['quoted-checkpoint-transfer-v1', subject, case]))
    middle = len(ordered) // 2
    if middle == 0 or len(set(ordered)) != len(ordered):
        raise ValueError('Both folds need distinct original holdout cases')
    return tuple(sorted(ordered[:middle])), tuple(sorted(ordered[middle:]))


def prepare(cohort):
    plan, eager_fit = discovery.discovery_contract()
    fitted = json.loads(transfer.read_locked(FIT, FIT_SHA))
    base, panels, models, static, _, _, choices, _ = discovery.prepare_target(cohort, plan, fitted, eager_fit)
    grouped = {}
    for subject, model, matrix in panels:
        grouped.setdefault(subject, {})[model] = matrix
    enrollment = {}
    for subject, versions in grouped.items():
        counts = {len(matrix[0]) for matrix in versions.values()}
        if len(versions) != 2 or len(counts) != 1:
            raise ValueError('Each transfer task requires two aligned model panels')
        held = transfer.layouts.source.holdout(subject, counts.pop())
        enrollment[subject] = {'models': sorted(versions), 'folds': split_cases(subject, held)}
    train, audit = base['seeds'][::2], base['seeds'][1::2]
    if len(train) != len(audit) or set(train) & set(audit):
        raise ValueError('The two seed panels must be balanced and disjoint')
    source = Path(__file__).resolve()
    plan = {**base, 'protocol': 'quoted-schedule-checkpoint-transfer-v1', 'discoveryReceiptSha256': FIT_SHA,
            'sourceSha256': {**base['sourceSha256'], str(source.relative_to(transfer.ROOT)):
                             sha256(source.read_bytes()).hexdigest()},
            'nativeSearchCap': max(cap for _, _, _, cap in base['controls']), 'pairs': enrollment,
            'calibrationSeeds': train, 'auditSeeds': audit,
            'scope': 'Calibrate on one model, one half of the fixed original holdout and the even-position seeds. '
                     'Audit on the other model, the other half of the holdout and the odd-position seeds. '
                     'Reverse both directions. Fit quoted, eager and split-safe GEPA menus independently under '
                     'the same realized calibration router budget for the task and model. Carry only each '
                     'selected setting to audit. Report actual audit lookup totals and the shared hard cap. '
                     'Keep the original three-cycle search and qualification layouts.'}
    return plan, grouped, models, static, choices[adaptive.ADAPTIVE]['actions']


def layouts(plan, subject, matrix, seeds, held):
    for seed in seeds:
        start, stages = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
        if not set(held) <= set(stages[0][2][-1]):
            raise ValueError('Calibration and audit may only score fixed holdout cases')
        yield start, [(number, roster, (*roles[:3], held)) for number, roster, roles in stages]


def rollout(cells, start, stages, runner, cap):
    run = native.paired.cycle.execute_path
    paid = 0
    current = start
    if runner is not None:
        for seed, roster, roles in stages:
            measured, ledger = run(runner, cells, current, roster, roles, seed, cap, 1)
            continuous.routing.verify_qualification(cells, current, roles, measured, ledger, 1)
            current = measured.prompt
            paid += len(ledger)
    return paid, [cells[current][case] for case in stages[0][2][-1]]


def calibrate(plan, subject, matrix, held, engines, router):
    cells, packed = transfer.case_cells(matrix)
    cap = plan['nativeSearchCap']
    totals = {name: {setting: Counter() for setting in runners} for name, runners in engines.items()}
    first_changes, native_changes = {}, {}
    baseline, retained = Counter(), Counter()
    with native.split_safe_cache():
        for start, stages in layouts(plan, subject, matrix, plan['calibrationSeeds'], held):
            paid, grades = rollout(cells, start, stages, router, cap)
            baseline.update(paidLookups=paid, holdoutPasses=sum(grades))
            retained.update(paidLookups=0, holdoutPasses=sum(cells[start][case] for case in held))
            for name, runners in engines.items():
                for setting, runner in runners.items():
                    paid, grades = rollout(cells, start, stages, runner, cap)
                    totals[name][setting].update(paidLookups=paid, holdoutPasses=sum(grades))
            continuous.native_episode(packed, start, stages, cap, first_changes, native_changes)
    totals[GEPA] = {}
    transfer.tally_native(totals[GEPA], native_changes, cap)
    chosen = {}
    for name, menu in totals.items():
        menu[RETAIN] = retained
        labels = tuple(setting for setting in menu if setting != RETAIN)
        chosen[name] = native.gepa.best_fixed(menu, labels, baseline['paidLookups'])
    return chosen, baseline, {name: digest(points) for name, points in totals.items()}


def audit(plan, subject, matrix, held, engines, router, prefix, selected):
    cells, packed = transfer.case_cells(matrix)
    cap = plan['nativeSearchCap']
    eager = engines[EAGER].get(selected[QUOTED]['setting'])
    runners = {name: engines[name].get(selected[name]['setting']) for name in engines}
    runners.update({ROUTED: router, PREFIX: prefix, RETAIN: None, 'matched-eager': eager})
    totals = {name: Counter() for name in (*runners, GEPA)}
    vectors = {name: [0] * len(held) for name in totals}
    add = native.paired.frontier.transfer.fitted.prior.add_vector

    def record(name, paid, grades):
        totals[name].update(paidLookups=paid, holdoutPasses=sum(grades))
        add(vectors[name], grades)

    for start, stages in layouts(plan, subject, matrix, plan['auditSeeds'], held):
        for name, engine in runners.items():
            paid, grades = rollout(cells, start, stages, engine, cap)
            record(name, paid, grades)
        current, cost = start, 0
        for seed, roster, roles in stages:
            current, grades, spent = continuous.attaining_trial(selected[GEPA]['setting'], (packed, current, roster, roles, seed))
            if spent > cap + 2 * len(roles[2]):
                raise ValueError('Each native cycle must fit the common search and qualification allowance')
            cost += spent
        record(GEPA, cost, grades)
    if vectors[QUOTED] != vectors['matched-eager'] or totals[QUOTED]['paidLookups'] > totals['matched-eager']['paidLookups']:
        raise ValueError('The transferred quoted setting must preserve its matched eager grades and save or tie on cost')
    return totals, vectors


def measure(plan, tasks, models, static, frozen):
    router = adaptive.routed_runner(plan, models, static)
    quoted, eager = discovery.screens_with_quotes(plan), adaptive.screens(plan)
    prefix = partial(adaptive.cycle, actions=tuple(quoted[action] for action in frozen))
    names = [name for name, *_ in plan['controls']]
    engines = {label: {name: partial(_run, screen=screens[name]) for name in names}
               for label, screens in ((QUOTED, quoted), (EAGER, eager))}
    points, vectors, totals = {}, {}, {}
    for subject, geometry in plan['pairs'].items():
        checkpoints = geometry['models']
        folds = geometry['folds']
        points[subject] = []
        for index, model in enumerate(checkpoints):
            other = 1 - index
            calibration, budget, hashes = calibrate(plan, subject, tasks[subject][model], folds[index], engines, router)
            observed, scores = audit(plan, subject, tasks[subject][checkpoints[other]], folds[other], engines, router,
                                     prefix, calibration)
            vectors[f'{subject}/{other}'] = scores
            for name, values in observed.items():
                totals.setdefault(name, Counter()).update(values)
            points[subject].append({'calibrationModel': model, 'auditModel': checkpoints[other], 'calibrationFold': index,
                                    'auditFold': other, 'calibrationRouter': budget, 'calibrationSetting': calibration,
                                    'calibrationMenuSha256': hashes, 'audit': observed})
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {name: paired(vectors, QUOTED, name, plan) for name in totals if name != QUOTED}
    return {'auditEpisodes': 2 * len(tasks) * len(plan['auditSeeds']), 'directions': points, 'auditTotals': totals,
            'pairedQuoted': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=discovery.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
