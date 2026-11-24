"""Fit and transfer uniform case order using already-paid incumbent grades."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import bounded_uniform_price_audit as previous
from cpo._contract import digest
from cpo.ordered_uniform_validation import ORDERS, ORIGINAL, screen
from cpo.two_sided_certificate_cycle import _run


refit = previous.refit
discovery, native, transfer, parent = refit.discovery, refit.native, refit.transfer, refit.parent
WIDTH, ROW_COUNTS = 8, (2, 3)
SETTINGS = {f'uniform/{WIDTH}/{(WIDTH + 1) * rows}': (WIDTH + 1) * rows for rows in ROW_COUNTS}
AUDIT_SHA256 = '21dcd9af1989dafa2d749ff8508e9a84d9e4bb905f0e40123bca0b0ded670b04'


def source_hashes():
    root = transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/ordered_uniform_validation.py',
             root / 'cpo/bounded_uniform_validation.py')
    return {str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}


def contract():
    prior_plan, base, _ = refit.previous.contract()
    plan = {**prior_plan, 'protocol': 'ordered-uniform-fit-v1', 'settings': SETTINGS,
            'orders': ORDERS, 'priceAuditSha256': AUDIT_SHA256,
            'sourceSha256': {**prior_plan['sourceSha256'], **source_hashes()},
            'scope': 'Keep the funded case set and roster. Compare original order, incumbent misses first '
                     'and incumbent passes first at two fixed uniform depths. Charge every validation and '
                     'qualification read. Freeze the least expensive order at each depth on the original '
                     'task-disjoint discovery archive. Retain original order on ties.'}
    return plan, base


def cap_screen(incumbent, candidates, rows, evaluate, cap, *, nominal, order):
    return screen(incumbent, candidates[:WIDTH], rows, evaluate, min(cap, nominal), order=order)


def nomination(result):
    return result.search.finalist, result.search.prompt, result.qualification


def cycle(cells, incumbent, stage, runners, max_cap, funded):
    seed, roster, roles = stage
    run = native.paired.cycle.execute_path
    grades, costs, chosen = None, {}, None
    original_incumbent_reads = None
    for order, runner in runners.items():
        result, ledger = run(runner, cells, incumbent, roster, roles, seed, max_cap, 1)
        shared = [(prompt, case) for (role, prompt, case) in ledger
                  if role == 'validation' and prompt == incumbent]
        if order == ORIGINAL:
            grades, chosen = nomination(result), result.prompt
            original_incumbent_reads = shared
        elif nomination(result) != grades or shared != original_incumbent_reads:
            raise ValueError('Case ordering must preserve incumbent reads and the original complete decision')
        if any(role == 'validation' and case not in funded for role, _, case in ledger):
            raise ValueError('A challenger read cannot leave the original funded validation panel')
        costs[order] = len(ledger)
    return chosen, costs


def measure(plan, panels, vectors):
    max_cap = max(cap for _, _, _, cap in plan['controls'])
    runners = {setting: {order: partial(_run, screen=partial(cap_screen, nominal=nominal, order=order))
                         for order in ORDERS} for setting, nominal in plan['settings'].items()}
    totals = {setting: Counter() for setting in runners}
    counts = {setting: {order: Counter() for order in ORDERS} for setting in runners}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
        held = stages[0][2][-1]
        scores = vectors.setdefault(subject, {})
        for setting, policies in runners.items():
            current = start
            rows = plan['settings'][setting] // (WIDTH + 1)
            point = totals[setting]
            local = Counter()
            for stage in stages:
                funded = {str(case) for case in stage[2][1][:rows]}
                current,  prices = cycle(cells, current, stage, policies, max_cap, funded)
                local.update(prices)
                local['cycleOrderHindsight'] += min(prices.values())
                for order, cost in prices.items():
                    counts[setting][order].update(cheaper=int(cost < prices[ORIGINAL]),
                                                   dearer=int(cost > prices[ORIGINAL]))
            values = [cells[current][case] for case in held]
            point.update(local)
            point.update(holdoutPasses=sum(values), episodes=1)
            add(scores.setdefault(setting, [0] * len(values)), values)
    return totals, counts


def choose(points):
    """Choose the cheapest shared order across discovery cohorts."""
    charges = {order: sum(row[order] for row in points.values()) for order in ORDERS}
    selected = min(ORDERS, key=charges.__getitem__)
    return {'selectedOrder': selected, 'discoveryLookups': charges,
            'nonIncreasingInEveryDiscoveryCohort': [name for name in ORDERS
                                                      if all(row[name] <= row[ORIGINAL] for row in points.values())]}


def fit(plan, groups):
    results = {setting: {} for setting in plan['settings']}
    for cohort, panels in groups.items():
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        if not enrolled:
            continue
        point, _ = measure(plan, [panel for panel in panels if panel[:2] in enrolled], {})
        for setting, measured in point.items():
            results[setting][cohort] = measured
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'points': results, 'policies': {setting: choose(points) for setting, points in results.items()}}


def prepare(cohort, plan, fitted):
    if fitted['planSha256'] != digest(plan) or digest(fitted['plan']) != digest(plan):
        raise ValueError('The ordering policy must come from the sealed discovery fit')
    inherited, inputs = refit.perfect.prepare(cohort)
    prior = json.loads(transfer.read_locked('docs/bounded-uniform-price-audit-v1.json', AUDIT_SHA256))
    if digest(inherited) != prior['plan']['cohortPlanSha256'][cohort]:
        raise ValueError('The original uniform price audit must use this exact layout')
    choices = {setting: entry['selectedOrder'] for setting, entry in fitted['policies'].items()}
    if set(choices) != set(SETTINGS) or any(order not in ORDERS for order in choices.values()):
        raise ValueError('Use only fitted case orders from the frozen menu')
    target = {**inherited, 'protocol': 'ordered-uniform-transfer-v1', 'fitSha256': digest(fitted),
              'selectedOrders': choices, 'settings': SETTINGS, 'priceAuditSha256': AUDIT_SHA256,
              'sourceSha256': {**inherited['sourceSha256'], **source_hashes()},
              'scope': 'Evaluate each frozen candidate read order on the same task-disjoint cohorts and '
                       'compare the selected order with the original score bound at total actual cost.'}
    return target, (*inputs[:-1], prior['results'][cohort])


def replay(plan, panels, _models, _static, gepa, simple, frontier, prior):
    vectors = {}
    points, counts = measure(plan, panels, vectors)
    frozen = points[previous.SETTING]
    if frozen[ORIGINAL] != prior['boundedLookups'] or frozen['holdoutPasses'] != prior['holdoutPasses']:
        raise ValueError('The original two-case uniform path must reproduce the archived cost and score')
    replayed = {}
    paired = native.frozen.paired_effects.paired_effect
    for setting, point in points.items():
        selected = plan['selectedOrders'][setting]
        cost = point[selected]
        pool = {subject: dict(scores) for subject, scores in vectors.items()}
        controls = parent.compare_simple(plan, panels, simple, cost, pool)
        bounds, anchors = parent.compare_native(plan, panels, gepa, cost,
                                                 simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], pool)
        replayed[setting] = {'selectedOrder': selected, 'withinBaselineBudget': cost <= frontier['budget'],
                            'simpleAtBudget': controls, 'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors,
                            'paired': {other: paired(pool, setting, other, plan) for other in (*controls, *anchors)}}
    return {'points': points, 'perOrderCycleChanges': counts, 'comparisonAtSelectedPrice': replayed,
            'boundedOpeningBudget': frontier['budget']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, base = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, inputs = prepare(args.cohort, plan, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, _, _ = discovery.training(base)
        receipt = fit(plan, groups)
    else:
        receipt = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
