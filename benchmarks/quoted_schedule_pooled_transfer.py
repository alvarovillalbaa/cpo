"""Choose and execute a task portfolio under a hard pooled lookup budget."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import quoted_schedule_realized_frontier as frontier
from cpo._contract import digest
from cpo.two_sided_certificate_cycle import _run


guard, parent = frontier.guard, frontier.parent
native, adaptive, transfer = frontier.native, frontier.adaptive, frontier.transfer
RETAIN, PREFIX, GUARDED = guard.RETAIN, guard.PREFIX, guard.GUARDED
PRIMARY, LOCAL, EAGER = 'pooled-quoted', 'local-quoted', 'pooled-eager'
PROTECTED = 'pooled-with-local-floor'
RECEIPTS = dict(zip(parent.discovery.COHORTS, (
    '7e0bf33a10b851a03658908c380a69a29cc7dd4b1e33996b687e44d7bb099dbf',
    '5bc93e817aea4eab063ad62ee47384acabe7a1edef7d6ee083296851ae00c9d5',
    '66ba6240089666e1243cb8da169c984cdc42dde3742c5ffa5973181cd0b7d771',
    '37959a71dee88131ee9588fe6c9dc2b3b9924c0a3f78c6ab946157b46c248f66',
    'efaa92b934d26f478b164575d155198b0cbd161e1fe83e6721e3e14a7a21a573',
    'fcfca36686437db45f0a44310f6635a31ff8b2522e6f12bc1bfea1bd1794ec37',
    '5efbc942e060d3bf2854a4cfd17a60abd04c38f83cc9b711ec8ffb0728a8a7f2',
), strict=True))


def prepare(cohort):
    base, tasks, frozen, checkpoint, reference = frontier.prepare(cohort)
    lock = RECEIPTS[cohort]
    path = f'docs/quoted-schedule-realized-frontier-{cohort.lower()}-v1.json'
    receipt = json.loads(transfer.read_locked(path, lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('The paid budget and audit layouts must match the exact previous frontier')
    audit_budget = receipt['results']['pricedPolicies'][GUARDED]['paidLookups']
    source = Path(__file__).resolve()
    plan = {**base, 'protocol': 'quoted-schedule-pooled-transfer-v1', 'frontierReceiptSha256': lock,
            'sourceSha256': {**base['sourceSha256'], str(source.relative_to(transfer.ROOT)):
                             sha256(source.read_bytes()).hexdigest()},
            'auditBudget': audit_budget,
            'scope': 'Use only the original opposite-model calibration cases and seeds to select one action per '
                     'audit direction from quoted simple schedules, the frozen prefix and retention. Fit at the '
                     'smaller of the published audit budget and total calibration router price. Compare a pooled '
                     'fit with proportional budgets per direction and with the same pooled fit using eager charges. '
                     'A second pooled fit preserves the local setting’s calibration score on both halves of '
                     'each direction’s calibration cases before allocating any of its budget. '
                     'On the original audit cases, interleave directions by seed and reserve a full independent '
                     'qualification before each cycle. Clip the next search cap to the remaining cohort budget. '
                     'Reference the archived common and mixed alternatives at the externally fixed audit ceiling.'}
    return plan, tasks, frozen, checkpoint, reference, receipt['results']


def apportion(weights, budget):
    total = sum(weights.values())
    if not total:
        if budget:
            raise ValueError('A positive budget needs a nonzero allocation weight')
        return dict.fromkeys(weights, 0)
    fractions = {name: divmod(budget * value, total) for name, value in weights.items()}
    result = {name: share for name, (share, _) in fractions.items()}
    remaining = budget - sum(result.values())
    order = sorted(weights, key=lambda name: (-fractions[name][1], name))
    for name in order[:remaining]:
        result[name] += 1
    return result


def search_allowance(available, desired, validation_rows, qualification_rows):
    allowance = min(desired, available - 2 * qualification_rows)
    return allowance if allowance >= validation_rows else 0


def protect_local(points, vectors, local_setting, halves, budget):
    def score(setting, half):
        return sum(vectors[setting][index] for index in half)

    floors = tuple(score(local_setting, half) for half in halves)
    return {setting: point if all(score(setting, half) >= floor for half, floor in zip(halves, floors, strict=True))
            else {'holdoutPasses': 0, 'paidLookups': budget + 1} for setting, point in points.items()}


def fit_portfolio(points, budget):
    labels = tuple(name for name in next(iter(points.values())) if name != RETAIN)
    ceiling = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    fitted = ceiling(points, labels, {'fit': budget})['fit']
    return {'settingsByDirection': fitted['settingsBySubject'], 'holdoutPasses': fitted['holdoutPasses'],
            'paidLookups': fitted['paidLookups']}


def engines(plan, frozen):
    caps = {name: limit for name, _, _, limit in plan['controls']}
    caps.update({RETAIN: 0, PREFIX: plan['fullRosterCap']})
    quoted, eager = parent.discovery.screens_with_quotes(plan), adaptive.screens(plan)
    menus = {}
    for label, screens in ((PRIMARY, quoted), (EAGER, eager)):
        table = {name: partial(_run, screen=screens[name]) for name, *_ in plan['controls']}
        table[PREFIX] = partial(adaptive.cycle, actions=tuple(screens[action] for action in frozen))
        table[RETAIN] = None
        menus[label] = table
    return caps, menus


def calibrate(plan, tasks, checkpoint, menus):
    points = {label: {} for label in menus}
    prices, scores, folds = {}, {}, {}
    for subject, rows in checkpoint['directions'].items():
        for row in rows:
            name = f"{subject}/{row['auditFold']}"
            matrix = tasks[subject][row['calibrationModel']]
            scored = plan['pairs'][subject]['folds'][row['calibrationFold']]
            prices[name] = row['calibrationRouter']['paidLookups']
            for label, runners in menus.items():
                points[label][name], grades = guard.score(plan, subject, matrix, scored, plan['calibrationSeeds'], runners)
                if label == PRIMARY:
                    mapping = {case: index for index, case in enumerate(scored)}
                    halves = parent.split_cases(f'{subject}/pooled-floor', scored)
                    folds[name] = tuple(tuple(mapping[case] for case in half) for half in halves)
                    scores[name] = grades
    budget = min(plan['auditBudget'], sum(prices.values()))
    limits = apportion(prices, budget)
    fit = {label: fit_portfolio(menu, budget) for label, menu in points.items()}
    local = {name: native.gepa.best_fixed(table, tuple(setting for setting in table if setting != RETAIN), limits[name])
             for name, table in points[PRIMARY].items()}
    fit[LOCAL] = {'settingsByDirection': {name: item['setting'] for name, item in local.items()},
                  **{key: sum(item[key] for item in local.values()) for key in ('holdoutPasses', 'paidLookups')}}
    points[PROTECTED] = {name: protect_local(menu, scores[name], local[name]['setting'], folds[name], budget)
                         for name, menu in points[PRIMARY].items()}
    fit[PROTECTED] = fit_portfolio(points[PROTECTED], budget)
    if fit[PROTECTED]['holdoutPasses'] < fit[LOCAL]['holdoutPasses']:
        raise ValueError('Protecting local scores must leave the local portfolio feasible')
    return fit, budget, limits, {label: digest(menu) for label, menu in points.items()}


def audit_inputs(plan, tasks, checkpoint):
    inputs = {}
    for subject, rows in checkpoint['directions'].items():
        for row in rows:
            fold = row['auditFold']
            held = plan['pairs'][subject]['folds'][fold]
            matrix = tasks[subject][row['auditModel']]
            cells, _ = transfer.case_cells(matrix)
            layout = tuple(parent.layouts(plan, subject, matrix, plan['auditSeeds'], held))
            inputs[f'{subject}/{fold}'] = cells, held, layout
    return inputs


def audit(plan, inputs, schedule, caps, runners):
    run = native.paired.cycle.execute_path
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    verify = parent.continuous.routing.verify_qualification
    budget = plan['auditBudget']
    vectors = {name: [0] * len(held) for name, (_, held, _) in inputs.items()}
    total = Counter(paidLookups=0)
    audit_by_direction = {name: Counter(paidLookups=0, holdoutPasses=0) for name in inputs}
    ordered = sorted(inputs)
    for index, seed in enumerate(plan['auditSeeds']):
        order = sorted(ordered, key=lambda name: digest(['quoted-pooled-order-v1', seed, name]))
        for direction in order:
            cells, held, episodes = inputs[direction]
            current, stages = episodes[index]
            setting = schedule[direction]
            target = caps[setting]
            point = audit_by_direction[direction]
            for local_seed, roster, roles in stages:
                if setting == RETAIN:
                    break
                cap = search_allowance(budget - total['paidLookups'], target, len(roles[1]), len(roles[2]))
                point.update(clippedCycles=int(cap < target), unfundedCycles=int(cap == 0))
                if not cap:
                    continue
                result, ledger = run(runners[setting], cells, current, roster, roles, local_seed, cap, 1)
                verify(cells, current, roles, result, ledger, 1)
                paid = len(ledger)
                if paid > cap + 2 * len(roles[2]) or total['paidLookups'] + paid > budget:
                    raise ValueError('A cycle exceeded its reserved search and qualification allowance')
                total['paidLookups'] += paid
                point['paidLookups'] += paid
                current = result.prompt
            grades = [cells[current][case] for case in held]
            add(vectors[direction], grades)
            point['holdoutPasses'] += sum(grades)
    total['holdoutPasses'] = sum(point['holdoutPasses'] for point in audit_by_direction.values())
    return {'totals': total, 'unusedLookups': budget - total['paidLookups'], 'byDirection': audit_by_direction}, vectors


def measure(plan, tasks, frozen, checkpoint, reference, frontier_result):
    caps, menus = engines(plan, frozen)
    fit, allowance, limits, hashes = calibrate(plan, tasks, checkpoint, menus)
    inputs = audit_inputs(plan, tasks, checkpoint)
    vectors = {name: {} for name in inputs}
    evaluation = {}
    for policy, attainer in fit.items():
        runners = menus[EAGER if policy == EAGER else PRIMARY]
        measured, scores = audit(plan, inputs, attainer['settingsByDirection'], caps, runners)
        evaluation[policy] = measured
        for name in scores:
            vectors[name][policy] = scores[name]
    comparisons = {name: native.frozen.paired_effects.paired_effect(vectors, PRIMARY, name, plan)
                   for name in (LOCAL, EAGER)}
    protected = {name: native.frozen.paired_effects.paired_effect(vectors, PROTECTED, name, plan)
                 for name in (LOCAL, PRIMARY)}
    baseline = reference['auditTotals'][GUARDED]
    if baseline != frontier_result['pricedPolicies'][GUARDED] or baseline['paidLookups'] != plan['auditBudget']:
        raise ValueError('The previous guarded result must price this audit ceiling exactly')
    opted = frontier_result['comparisons'][GUARDED]
    return {'auditEpisodes': reference['auditEpisodes'], 'calibrationBudget': allowance, 'localLimits': limits,
            'calibrationMenuSha256': hashes, 'fit': fit, 'audit': evaluation, 'pairedPooled': comparisons,
            'pairedProtected': protected,
            'guardedReference': baseline,
            'optimaAtBudget': {menu: {mode: {key: value[key] for key in ('holdoutPasses', 'paidLookups')}
                                      for mode, value in scopes.items()} for menu, scopes in opted.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=parent.discovery.COHORTS, required=True)
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
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
