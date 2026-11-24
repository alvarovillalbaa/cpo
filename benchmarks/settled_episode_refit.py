"""Refit episode schedules with misses-first validation and settled probes."""

import argparse
from collections import Counter
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import bounded_uniform_refit as refit
from benchmarks import ordered_uniform_transfer as ordered
from cpo._contract import digest
from cpo.ordered_uniform_validation import MISSES, screen
from cpo.settled_episode_schedule import choose_schedule
from cpo.two_sided_certificate_cycle import _run


discovery, native, parent, transfer = refit.discovery, refit.native, refit.parent, refit.transfer
previous, frontier = refit.previous, refit.frontier
BOUNDED, RETAIN = refit.BOUNDED, refit.RETAIN
FIXED, EAGER = refit.MODES
SETTLED, SETTLED_EAGER = 'settled-two', 'settled-two-with-full-probes'
FIT_SHA = '24b31f4461c9aeb1219e123c6a2adeac483255d7571236c9e1b30cd0ba8d0eb9'
ORDER_SHA = '8500258a3eeb8df7d551d9fd77ad4f7dca1f36a8ebe60814f9eb22b3cc89a939'
LOCKS = dict(zip(discovery.COHORTS, (
    '5dad85339cc3781e8873e9a12072ae250d9065fe3dfbc40f1c4258dc0eaffd7b',
    'f263585c50800f3687868cf7c209e28ecb00e251747cd02b75dd2ddd452abf8c',
    '79fd551de05431f2a5d847ecc6b098602f94086a275254078195d31754eee7da',
    'bfe8c82d202683b2f1de83f4333cb9242124707a87203261d36b0549c1a365c6',
    '3a9ac640dd902c5ed1c678063a5574565336da4a3d552da6704532da2ba6db42',
    'a8410b2c5d44fc5ef7b6f03435a3494054f3db02d38d191cf0418436b640629b',
    '5990f6a59d9ceda5875ffbb97dc3a363c6c43fc801a8d4656598ed81966db98d',
), strict=True))


def contract():
    context = refit.contract()
    baseline = json.loads(transfer.read_locked('docs/bounded-uniform-refit-v1.json', FIT_SHA))
    ordering = json.loads(transfer.read_locked('docs/ordered-uniform-fit-v1.json', ORDER_SHA))
    earlier = context[0]
    if digest(earlier) != baseline['planSha256'] or digest(baseline['plan']) != baseline['planSha256']:
        raise ValueError('The earlier episode refit must reproduce')
    ordering_plan, _ = ordered.contract()
    if (digest(ordering_plan) != ordering['planSha256'] or digest(ordering['plan']) != ordering['planSha256']
            or {policy['selectedOrder'] for policy in ordering['policies'].values()} != {MISSES}):
        raise ValueError('Both measured uniform depths must select misses-first')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), Path(refit.__file__), root / 'cpo/ordered_uniform_validation.py',
             root / 'cpo/settled_episode_schedule.py')
    plan = {**earlier, 'protocol': 'settled-episode-refit-v1', 'refitReceiptSha256': FIT_SHA,
            'orderReceiptSha256': ORDER_SHA, 'uniformOrder': MISSES,
            'sourceSha256': {**earlier['sourceSha256'],
                             **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}},
            'scope': 'Reprice the fixed menu by using misses-first within each originally funded uniform '
                     'case set. Fit constant, full two-probe and settled two-probe episode policies. '
                     'Use the same discovery tasks and bounded opening per-cohort budgets. Verify that '
                     'settling a branch skips only replies that cannot change the table action.'}
    return plan, context, baseline


def limit(incumbent, candidates, rows, evaluate, cap, *, width, maximum):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, maximum), order=MISSES)


def engines(plan, models, static):
    original, optimized = refit.engines(plan, models, static)
    reordered = {name: partial(_run, screen=partial(limit, width=width, maximum=cap))
                 for name, mode, width, cap in plan['controls'] if mode == 'uniform'}
    return {**original, **optimized}, reordered


def episode(plan, cells, stages, start, original, reordered):
    cap = max(limit for _, _, _, limit in plan['controls'])
    run = native.paired.cycle.execute_path
    held = stages[0][2][-1]

    @cache
    def rollout(label):
        current, old, new = start, 0, 0
        if label == RETAIN:
            return [cells[current][row] for row in held], old, new
        for seed, roster, roles in stages:
            args = cells, current, roster, roles, seed, cap, 1
            decision, ledger = run(original[label], *args)
            cost = len(ledger)
            old += cost
            if label in reordered:
                result, paid = run(reordered[label], *args)
                if ordered.nomination(result) != ordered.nomination(decision):
                    raise ValueError('The uniform case order must preserve the exact qualification and nominee')
                cost = len(paid)
            new += cost
            current = decision.prompt
        return [cells[current][row] for row in held], old, new

    return rollout


def probe_cost(actions, first_fail, first_pass, *, settled):
    if not settled:
        return 2 * (first_fail + first_pass)
    zero, one, two = actions
    if zero == one == two:
        return 0
    return first_fail * (1 + (zero != one)) + first_pass * (1 + (one != two))


def fit_table(rows, options, budgets, min_subjects, *, settled):
    cohorts = tuple(budgets)
    panels = {key: Counter() for key in cohorts}
    supports = [set() for _ in range(3)]
    states = [{label: {cohort: Counter() for cohort in cohorts} for label in options} for _ in range(3)]
    for cohort, subject, pair, menu in rows:
        state = sum(pair)
        supports[state].add(subject)
        panels[cohort][pair[0]] += 1
        for label, point in menu.items():
            states[state][label][cohort].update(holdoutPasses=point.passes, paidLookups=point.cost)
    choices = [options if len(support) >= min_subjects else (RETAIN,) for support in supports]
    best, feasible, chosen = None, 0, None
    for actions in product(*choices):
        columns = [table[action] for table, action in zip(states, actions, strict=True)]
        prices = []
        for cohort in cohorts:
            overhead = probe_cost(actions, panels[cohort][False], panels[cohort][True], settled=settled)
            prices.append(sum(state[cohort]['paidLookups'] for state in columns) + overhead)
        if any(cost > budgets[cohort] for cost, cohort in zip(prices, cohorts, strict=True)):
            continue
        scores = [sum(state[cohort]['holdoutPasses'] for state in columns) for cohort in cohorts]
        rank = (-sum(scores), sum(prices), actions)
        feasible += 1
        if best is None or rank < best:
            best = rank
            chosen = {'actions': actions, 'points': {cohort: {'holdoutPasses': score, 'paidLookups': cost}
                                                    for cohort, score, cost in zip(cohorts, scores, prices, strict=True)}}
    if chosen is None:
        raise ValueError('No table fits the per-cohort budgets')
    return {**chosen, 'feasibleTables': feasible, 'support': list(map(len, supports))}


def fit(plan, groups, models, static, baseline):
    engines_in_use = engines(plan, models, static)
    options = tuple(sorted(engines_in_use[0]))
    budgets = {key: value['paidLookups'] for key, value in baseline['baseline'].items()}
    old_rows, new_rows, fixed_rows = [], [], []
    for cohort in budgets:
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in enrolled]
        for subject, _, _, cells, stages, start in previous.episodes(plan, panels):
            rollout = episode(plan, cells, stages, start, *engines_in_use)
            before, after = {}, {}
            for label in options:
                grades, old, new = rollout(label)
                score = sum(grades)
                before[label] = frontier.Point(score, old, (label,))
                after[label] = frontier.Point(score, new, (label,))
            rollout.cache_clear()
            _, ledger = previous.probe(EAGER, plan['probeModes'], cells, stages, start)
            pair = tuple(grade for _, _, grade in ledger)
            old_rows.append((cohort, subject, pair, before))
            new_rows.append((cohort, subject, pair, after))
            fixed_rows.append((cohort, subject, '0', 0, after))
    archived = baseline['optimizedFits'][EAGER]
    check = fit_table(old_rows, options, budgets, plan['minSubjectsPerState'], settled=False)
    if (check['actions'] != tuple(archived['actions'][str(i)] for i in range(3))
            or check['points'] != archived['points'] or check['feasibleTables'] != archived['feasibleTables']):
        raise ValueError('The solver must reproduce the earlier full-probe fit and budget accounting')
    fixed = previous.fit_table(fixed_rows, options, budgets, plan['minSubjectsPerState'])
    policies = {FIXED: {**fixed, 'actions': (fixed['actions']['0'],) * 3},
                EAGER: fit_table(new_rows, options, budgets, plan['minSubjectsPerState'], settled=False),
                SETTLED: fit_table(new_rows, options, budgets, plan['minSubjectsPerState'], settled=True)}
    points = {BOUNDED: baseline['baseline'], **{name: value['points'] for name, value in policies.items()}}
    winner = min(points, key=lambda key: (refit.depth.rank(points[key]), key != BOUNDED, key))
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'fitted': policies,
            'selected': winner, 'baseline': baseline['baseline'], 'budget': budgets}


def target(cohort, plan, context, baseline, fitted):
    if fitted['planSha256'] != digest(plan) or digest(fitted['plan']) != digest(plan):
        raise ValueError('Use the sealed discovery fit')
    prior_plan, prior_data = refit.target(cohort, context[0], context[1], context[3], baseline)
    lock = LOCKS[cohort]
    prior = json.loads(transfer.read_locked(f'docs/bounded-uniform-refit-transfer-{cohort.lower()}-v1.json', lock))
    if digest(prior_plan) != prior['planSha256']:
        raise ValueError('The score-bound episode study must reproduce')
    new_plan = {**prior_plan, 'protocol': 'settled-episode-refit-transfer-v1', 'uniformOrder': MISSES,
                'settledFitSha256': digest(fitted), 'priorRefitReceiptSha256': lock, 'selectedPolicy': fitted['selected'],
                'revisedActions': {name: entry['actions'] for name, entry in fitted['fitted'].items()},
                'sourceSha256': {**prior_plan['sourceSha256'], **plan['sourceSha256']},
                'scope': 'Replay the original constant and full-probe reference schedules. Compare the '
                         'new constant, full-probe and settled-probe tables at their actual cost. Verify '
                         'the settled table with a full-probe replay of its same decisions.'}
    return new_plan, (*prior_data[:-1], prior['results'])


def route(cells, stages, start, actions):
    ledger = []

    def observe(prompt, case):
        grade = bool(cells[prompt][case])
        ledger.append((prompt, case, grade))
        return grade

    choice = choose_schedule(start, stages[0][2][0][:2], observe, actions=actions)
    return choice, ledger


def replay(plan, panels, models, static, gepa, simple, prior):
    tally = (BOUNDED, 'previous-two', FIXED, EAGER, SETTLED, SETTLED_EAGER)
    totals, choices = ({name: Counter() for name in tally} for _ in range(2))
    engines_in_use = engines(plan, models, static)
    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, _, _, cells, stages, start in previous.episodes(plan, panels):
        rollout = episode(plan, cells, stages, start, *engines_in_use)
        state, ledger = previous.probe(EAGER, plan['probeModes'], cells, stages, start)
        settled = plan['revisedActions'][SETTLED]
        action, used = route(cells, stages, start, settled)
        if (action != settled[int(state)] or used != ledger[:len(used)]
                or len(used) != probe_cost(settled, int(not ledger[0][2]), int(ledger[0][2]), settled=True)):
            raise ValueError('Settled probe execution and fitted lookup counts must agree')
        chosen = {BOUNDED: (BOUNDED, 0, False),
                  'previous-two': (plan['optimizedActions'][EAGER][state], len(ledger), False),
                  FIXED: (plan['revisedActions'][FIXED][0], 0, True),
                  EAGER: (plan['revisedActions'][EAGER][int(state)], len(ledger), True),
                  SETTLED: (action, len(used), True), SETTLED_EAGER: (settled[int(state)], len(ledger), True)}
        for name, (setting, cost, cheaper) in chosen.items():
            grades, before, after = rollout(setting)
            totals[name].update(holdoutPasses=sum(grades), paidLookups=cost + (after if cheaper else before),
                                trainingLookups=cost)
            choices[name][setting] += 1
            add(vectors.setdefault(subject, {}).setdefault(name, [0] * len(grades)), grades)
        rollout.cache_clear()
    if totals[BOUNDED] != prior['policies'][BOUNDED] or totals['previous-two'] != prior['policies'][f'{EAGER}/refit']:
        raise ValueError('The original bounded and score-bound reference policies must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name in (FIXED, EAGER, SETTLED):
        grades = {subject: dict(scores) for subject, scores in vectors.items()}
        spend = totals[name]['paidLookups']
        controls = parent.compare_simple(plan, panels, simple, spend, grades)
        bounds, anchors = parent.compare_native(plan, panels, gepa, spend,
                                                 simple['settingsTotals'][RETAIN]['holdoutPasses'], grades)
        comparisons[name] = {'simpleAtBudget': controls, 'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors,
                             'withinBoundedBudget': spend <= totals[BOUNDED]['paidLookups'],
                             'paired': {other: paired(grades, name, other, plan)
                                        for other in (BOUNDED, 'previous-two', *controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals,
            'decisions': choices, 'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, context, baseline = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, inputs = target(args.cohort, plan, context, baseline, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, models, static = discovery.training(context[2])
        report = fit(plan, groups, models, static, baseline)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
