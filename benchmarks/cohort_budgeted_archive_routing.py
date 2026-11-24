"""Fit one paid routing table under separate discovery cohort budgets."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import paid_prefix_archive_routing as previous
from cpo._contract import digest


transfer = previous.transfer
STATIC, POOLED = previous.STATIC, previous.PROBE
BUDGETED, NONLOSS = 'cohort-budgeted', 'cohort-nonloss'
POLICIES = (BUDGETED, NONLOSS)
EXTRA = 'additional-MMLU'
COHORTS = (*transfer.COHORTS, EXTRA)
BASE = previous.BUDGET_CONTROL
ACTIONS = tuple(sorted(previous.SCREENS))
FIT_RECEIPT = 'docs/paid-prefix-archive-routing-fit-v1.json'
FIT_SHA = '23f78bb833491e0f588f55997eebd87c1dca940ef106999089936feab2dadceb'
PRIOR_REPORTS = dict(zip(transfer.COHORTS, (
    '78d00f7838c4f05a0c004937cbbd7525a95c6d18e9d3b8c263a546d6d877ee78',
    'd89a18dddd92eec4692d83d34e4e97b7312e5d24f53f12b00de777c839c7ac8f',
    'd9668c742c74daf80a321384a6e1c6f06c1390ce4b8b78816b4eae83b055e077',
    'c74d9d0a427fc065a7d7593c8b0c9d4531c831a811209f08f2cb435720ab5793',
    'e81e3e73e668805929d42f6510e5fa754d9afc14e75704e1955ddf1fde3aa528',
    '044d9bba75b28b4c55907b8fcfd5ae4a8cb95cf13f6ad6b91690e4c390e15c6e',
), strict=True))
EXTRA_ARCHIVES = {
    'low-budget-transfer-v1.json': 'f28ec5f717137e179be0265b4236b1d034bebc5a1d1ce0273cbef56ab7c83d60',
    'late-miss-transfer-v1.json': '751ba960d8c8e8ed109316724a1fb0e988d2c841b7468cd8650b30228934f953',
}


def read_json(name, sha):
    return json.loads(transfer.read_locked(name, sha))


def training_plan():
    inherited, discovery = previous.training_plan()
    pooled = read_json(FIT_RECEIPT, FIT_SHA)
    if pooled['planSha256'] != digest(inherited) or digest(pooled['plan']) != digest(inherited):
        raise ValueError('The original pooled fit must match its source plan')
    plan = {**inherited, 'protocol': 'cohort-budgeted-archive-routing-fit-v1',
            'parentPlanSha256': pooled['planSha256'], 'pooledFitSha256': FIT_SHA,
            'budgetedSourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'policies': {BUDGETED: {'budgetPercent': 95, 'requireNonloss': False},
                         NONLOSS: {'budgetPercent': 100, 'requireNonloss': True}},
            'scope': 'Fit the existing paid lookup router on discovery outcomes only. Enforce a separate cap on '
                     'each discovery cohort. Within those caps maximize total passes, minimize total lookups and '
                     'break exact ties lexicographically. The nonloss control also requires every discovery cohort '
                     'to match or exceed its incumbent-first score. The deployed table uses no cohort labels.'}
    return plan, discovery, pooled


def cohort_menus(plan, discovery, panels, labels):
    label = labels[1]
    menus, closed, original = {}, {}, {}
    for cohort, entries in panels.items():
        menu = menus.setdefault(cohort, {})
        closed[cohort], original[cohort] = Counter(), Counter()
        for subject, model_name, matrix in entries:
            cells, _ = transfer.case_cells(matrix)
            traces = []
            for seed in plan['seeds']:
                start, roster, roles = transfer.layouts.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
                args = cells, start, roster, roles, seed, plan['fullRosterCap'], 1
                state = []

                def record(observed):
                    state.append(observed)
                    return BASE

                point, _, trace = previous.replay_point(args, POOLED, record)
                original[cohort].update(point)
                traces.append(trace)
                if not state:
                    closed[cohort].update(point)
                    continue
                observed, = state
                points = menu.setdefault(observed, {action: Counter() for action in ACTIONS})
                points[BASE].update(point)
                for action in ACTIONS:
                    if action != BASE:
                        point, _, _ = previous.replay_point(args, POOLED, lambda _: action)
                        points[action].update(point)
            expected = discovery['results'][cohort]['traceHashes'][f'{subject}/{model_name}'][label][BASE]
            if digest(traces) != expected:
                raise ValueError('Paying for the feature must reproduce the original incumbent-first paths')
    return menus, closed, original


def fit_table(menus, closed, original, budget_percent, require_nonloss, actions=ACTIONS):
    cohorts = tuple(sorted(menus))
    states = tuple(sorted(set().union(*(menu for menu in menus.values()))))
    budget = tuple(original[name]['paidLookups'] * budget_percent // 100 for name in cohorts)
    floor = tuple(original[name]['holdoutPasses'] if require_nonloss else 0 for name in cohorts)
    points = [{action: tuple(menus[name].get(state, {}).get(action, Counter()) for name in cohorts)
               for action in actions} for state in states]
    cost = [{action: tuple(p['paidLookups'] for p in row) for action, row in point.items()} for point in points]
    score = [{action: tuple(p['holdoutPasses'] for p in row) for action, row in point.items()} for point in points]
    size = len(states)
    min_cost = [(0,) * len(cohorts)] * (size + 1)
    max_score = [(0,) * len(cohorts)] * (size + 1)
    for index in range(size - 1, -1, -1):
        min_cost[index] = tuple(tail + min(column) for tail, column in
                                zip(min_cost[index + 1], zip(*cost[index].values()), strict=True))
        max_score[index] = tuple(tail + max(column) for tail, column in
                                 zip(max_score[index + 1], zip(*score[index].values()), strict=True))
    best, recorded = None, None

    def search(index, spent, earned, choices):
        nonlocal best, recorded
        if any(now + rest > limit for now, rest, limit in zip(spent, min_cost[index], budget, strict=True)):
            return
        if any(now + rest < minimum for now, rest, minimum in zip(earned, max_score[index], floor, strict=True)):
            return
        if best is not None and sum(earned) + sum(max_score[index]) < -best[0]:
            return
        if index == size:
            rank = (-sum(earned), sum(spent), choices)
            if best is None or rank < best:
                best, recorded = rank, (spent, earned)
            return
        for action in actions:
            search(index + 1, tuple(map(sum, zip(spent, cost[index][action], strict=True))),
                   tuple(map(sum, zip(earned, score[index][action], strict=True))), (*choices, action))

    search(0, tuple(closed[name]['paidLookups'] for name in cohorts),
           tuple(closed[name]['holdoutPasses'] for name in cohorts), ())
    if recorded is None:
        raise ValueError('No table satisfies the discovery budget and score constraints')
    return {'actions': dict(zip(states, best[2], strict=True)),
            'byCohort': {name: {'holdoutPasses': passes, 'paidLookups': spent, 'budget': limit}
                         for name, spent, passes, limit in zip(cohorts, *recorded, budget, strict=True)}}


def fit(plan, discovery):
    _, panels, labels, *_ = transfer.native.prepare()
    menus, closed, base = cohort_menus(plan, discovery, panels, labels)
    models = {name: fit_table(menus, closed, base, policy['budgetPercent'], policy['requireNonloss'])
              for name, policy in plan['policies'].items()}
    return {'plan': plan, 'planSha256': digest(plan), 'incumbentFirstByCohort': base, 'models': models,
            'menusSha256': digest(menus)}


def extra_panels(discovery, groups):
    used = {transfer.identity(*name.split('/')) for cohort in discovery['results'].values() for name in cohort['traceHashes']}
    used.update(transfer.identity(subject, model) for panels in groups.values() for subject, model, _ in panels)
    retained = []
    for filename, sha in EXTRA_ARCHIVES.items():
        rows = read_json(f'benchmarks/data/{filename}', sha)['panels']
        by_subject = {}
        for row in rows:
            by_subject.setdefault(row['subject'], []).append(row)
        for subject, pair in sorted(by_subject.items()):
            if len(pair) != 2 or len({row['caseOrderSha256'] for row in pair}) != 1:
                raise ValueError('Require a complete pair with matching case order')
            panels = {transfer.identity(subject, row['model']) for row in pair}
            if len(panels) != 2:
                raise ValueError('The panel models must be distinct')
            if panels & used:
                continue
            retained.extend((subject, row['model'], row['correctness']) for row in pair)
            used.update(panels)
    if len(retained) != 8:
        raise ValueError('The additional transfer must have eight previously unenrolled panels')
    return retained


def target_plan(cohort, trained, discovery):
    base, groups = transfer.prepare()
    original = None
    if cohort == EXTRA:
        panels = extra_panels(discovery, groups)
        identity = [(subject, model) for subject, model, _ in panels]
        base = {**base, 'cohorts': {**base['cohorts'], EXTRA: identity}, 'additionalArchiveSha256': EXTRA_ARCHIVES}
    else:
        panels = groups[cohort]
        path = f'docs/paid-prefix-archive-routing-{cohort.lower()}-v1.json'
        receipt = read_json(path, PRIOR_REPORTS[cohort])
        if receipt['plan']['fitSha256'] != digest(read_json(FIT_RECEIPT, FIT_SHA)):
            raise ValueError('The prior transfer must come from the original pooled fit')
        original = receipt['results']
    return {**base, 'protocol': 'cohort-budgeted-archive-routing-transfer-v1', 'cohort': cohort,
            'fitSha256': digest(trained), 'priorTransferReceiptSha256': PRIOR_REPORTS.get(cohort), 'minimumGains': (1,),
            'primaryByCohort': dict.fromkeys(COHORTS, BUDGETED),
            'gate': 'The primary must use no more than fitted static, have a positive paired lower endpoint '
                    'against fitted static and against common GEPA at matched budget, and exceed subject-tuned GEPA.'}, panels, original


def measure(plan, panels, trained, pooled, original):
    counts = {mode: Counter() for mode in (STATIC, POOLED, *POLICIES)}
    runners = {BASE: transfer.RUNNERS[BASE], 'certified-wide': transfer.RUNNERS['certified-wide'],
               STATIC: previous.fitted_runner(STATIC, pooled['models'], counts[STATIC]),
               POOLED: previous.fitted_runner(POOLED, pooled['models'], counts[POOLED])}
    fallback = pooled['models'][STATIC]
    for name in POLICIES:
        model = {STATIC: fallback, POOLED: trained['models'][name]}
        runners[name] = previous.fitted_runner(POOLED, model, counts[name])
    compare = transfer.compare_attainers
    effects = {}

    def paired_controls(panels, plan, vectors, schedules, expected, primary):
        paired = transfer.native.frozen.paired_effects.paired_effect
        for name in POLICIES:
            effects[name] = {control: paired(vectors, name, control, plan) for control in (STATIC, POOLED)}
        return compare(panels, plan, vectors, schedules, expected, primary)

    with patch.multiple(transfer, RUNNERS=runners, verify_witness=previous.verify_qualification,
                        compare_attainers=paired_controls):
        report = transfer.measure(panels, plan)
    points = report['cpo']['gain-1']
    if original is not None:
        if report['nativeSubjectTotalsSha256'] != original['nativeSubjectTotalsSha256']:
            raise ValueError('The exact native menu must reproduce before repricing')
        for name in (STATIC, POOLED, BASE, 'certified-wide'):
            if points[name] != original['cpo']['gain-1'][name] or any(
                traces['gain-1'][name] != original['panelPathHashes'][panel]['gain-1'][name]
                for panel, traces in report['panelPathHashes'].items()
            ):
                raise ValueError('Original transfer paths and totals must reproduce')
    report['primaryGatePassed'] &= (points[BUDGETED]['paidLookups'] <= points[STATIC]['paidLookups']
                                    and effects[BUDGETED][STATIC]['pairedRange95'][0] > 0)
    return {**report, 'pairedAgainstCpo': effects, 'actionCounts': counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit', type=Path)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--cohort', choices=COHORTS)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    frozen, discovery, pooled = training_plan()
    if args.fit is not None:
        if any((args.fitted, args.cohort, args.execute, args.out)) or args.fit.exists():
            parser.error('Fitting requires a fresh path and no transfer arguments')
        document = fit(frozen, discovery)
        output = args.fit
    else:
        if args.fitted is None or args.cohort is None:
            parser.error('Transfer requires a frozen fit and a cohort')
        trained = json.loads(args.fitted.read_bytes())
        if trained['planSha256'] != digest(frozen) or digest(trained['plan']) != digest(frozen):
            parser.error('Use a fit from the exact frozen discovery plan')
        plan, panels, original = target_plan(args.cohort, trained, discovery)
        seal = digest(plan)
        if args.execute is None and args.out is None:
            print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
            return
        if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
            parser.error('Replay requires the current seal, a fresh path and pinned GEPA')
        document = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
                    'results': measure(plan, panels, trained, pooled, original)}
        output = args.out
    with output.open('x') as out:
        json.dump(document, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
