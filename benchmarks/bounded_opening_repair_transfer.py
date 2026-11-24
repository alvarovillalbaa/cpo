"""Fit the first-row challenger budget together with the second-row repair."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import second_row_validation_transfer as second
from cpo._contract import digest
from cpo.bounded_opening_repair import screen
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.two_sided_certificate_cycle import _run


depth, discovery, adaptive = second.depth, second.discovery, second.adaptive
parent, native, transfer = second.parent, second.native, second.transfer
BASELINE, ROUTER = second.BASELINE, second.ROUTER
PRIMARY, CUT_ONLY, SAME_COST = 'fitted-opening-repair', 'fitted-cut-only', 'fitted-original-cost'
FIT_SHA = 'b0c2bfac01334011507a0f7d7be6895204e28b9b58bc2f21f4bc6f16e078be1e'


def contract():
    previous, base, archived, frozen = second.contract()
    prior_fit = json.loads(transfer.read_locked('docs/second-row-validation-fit-v1.json', FIT_SHA))
    if digest(previous) != prior_fit['planSha256'] or digest(prior_fit['plan']) != prior_fit['planSha256']:
        raise ValueError('The earlier second-row discovery contract must reproduce')
    widths = range(2, previous['width'], 2)
    additions = {f'{action}/{width}': (width, repair)
                 for action, repair in (('opening-limit', False), ('opening-limit-with-repair', True))
                 for width in widths}
    root = transfer.ROOT
    paths = (Path(__file__).resolve(), root / 'cpo/bounded_opening_repair.py')
    plan = {**previous, 'protocol': 'bounded-opening-repair-fit-v1', 'priorFitSha256': FIT_SHA,
            'additionalScreens': additions, 'oldChoices': previous['choices'],
            'choices': (*previous['choices'], *additions),
            'sourceSha256': {**previous['sourceSha256'],
                             **{str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in paths}},
            'scope': 'Fit every table of the previous choices plus opening miss width limits of 2, 4 or 6, '
                     'with and without a second-row repair on an opening pass. Freeze a table under the '
                     'original router caps, a width-only control under those caps, and a table with the '
                     'original quoted policy’s actual discovery cost as the cap in each discovery cohort. '
                     'Use the frozen disjoint tasks and no additional search cap or qualification probes.'}
    return plan, base, archived, frozen, prior_fit


def limit(incumbent, candidates, rows, evaluate, cap, *, width, maximum, opening_width, repair):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, maximum),
                  opening_width=opening_width, repair=repair)


def screens(plan):
    options = second.screens(plan)
    options.update({name: partial(limit, width=plan['width'], maximum=plan['cap'], opening_width=width, repair=repair)
                    for name, (width, repair) in plan['additionalScreens'].items()})
    return options


def choose(points, budgets, original):
    feasible = {table: per_cohort for table, per_cohort in points.items()
                if all(point['paidLookups'] <= budgets[cohort] for cohort, point in per_cohort.items())}
    selected = min(feasible, key=lambda table: (depth.rank(feasible[table]), table))
    if depth.rank(feasible[selected]) >= depth.rank(feasible[original]):
        selected = original
    return {'actions': selected, 'byCohort': feasible[selected], 'feasibleTables': len(feasible), 'budgets': budgets}


def fit(plan, groups, prior_fit):
    original = tuple(plan['baselineActions'])
    menu = [(original[0], *tail) for tail in product(plan['choices'], repeat=len(original) - 1)]
    engines = {name: partial(_run, screen=action) for name, action in screens(plan).items()}
    points = depth.sweep(plan, groups, menu, engines)
    original_points = points[original]
    prior_menu = {'|'.join(table): totals for table, totals in points.items()
                  if all(action in plan['oldChoices'] for action in table[1:])}
    if prior_menu != prior_fit['menu']:
        raise ValueError('Every earlier second-row discovery point must reproduce')
    simple = {plan['oldChoices'][0], *(action for action, (_, repair) in plan['additionalScreens'].items() if not repair)}
    cut = {table: totals for table, totals in points.items() if set(table[1:]) <= simple}
    matched = {cohort: point['paidLookups'] for cohort, point in original_points.items()}
    cap = prior_fit['budgets']
    policies = {PRIMARY: choose(points, cap, original), CUT_ONLY: choose(cut, cap, original),
                SAME_COST: choose(points, matched, original)}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'selected': policies[PRIMARY]['actions'], 'policies': policies, 'original': original_points,
            'evaluatedTables': len(points), 'cutOnlyTables': len(cut),
            'menuSha256': digest({'|'.join(table): totals for table, totals in points.items()})}


def target(cohort, plan, base, archived, frozen, fit_receipt):
    inherited, *inputs = second.target(cohort, plan, base, archived, frozen, fit_receipt)
    actions = {BASELINE: inherited['actions'][BASELINE], second.REPAIR: inherited['actions'][second.REPAIR],
               **{name: fit_receipt['policies'][name]['actions'] for name in (PRIMARY, CUT_ONLY, SAME_COST)}}
    original = tuple(plan['baselineActions'])
    if any(len(table) != len(original) or table[0] != original[0]
           or set(table[1:]) - set(plan['choices']) for table in actions.values()):
        raise ValueError('Every table must use the sealed menu')
    target_plan = {**inherited, 'protocol': 'bounded-opening-repair-transfer-v1',
                   'additionalScreens': plan['additionalScreens'], 'actions': actions,
                   'scope': 'Verify the original paid paths. Compare the original first-reply policy, '
                            'fixed full-width repair, and the three prospective choices. Price simple '
                            'controls and native anchors at each fitted policy’s actual lookup count.'}
    return target_plan, inputs


def replay(plan, panels, models, static, gepa, simple, prior):
    options = screens(plan)
    runners = {name: partial(run_qualification_prefix_cycle, screens=tuple(options[action] for action in table))
               for name, table in plan['actions'].items()}
    runners[ROUTER] = adaptive.routed_runner(plan, models, static)
    schedules = {name: dict.fromkeys(plan['subjects'], name) for name in runners}
    vectors = {}
    totals, hashes = adaptive.replay(plan, panels, runners, schedules, vectors)
    for name in (BASELINE, ROUTER):
        if totals[name] != prior['policies'][name] or any(
                paths[name] != prior['trajectoryHashes'][panel][name] for panel, paths in hashes.items()):
            raise ValueError('The existing first-reply and router traces must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name in (PRIMARY, CUT_ONLY, SAME_COST):
        spend = totals[name]['paidLookups']
        grades = {subject: dict(scores) for subject, scores in vectors.items()}
        controls = parent.compare_simple(plan, panels, simple, spend, grades)
        bounds, anchors = parent.compare_native(plan, panels, gepa, spend,
                                                 simple['settingsTotals'][adaptive.RETAIN]['holdoutPasses'], grades)
        peers = tuple(other for other in runners if other != name)
        comparisons[name] = {'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors, 'simpleAtBudget': controls,
                             'withinRouterCost': spend <= totals[ROUTER]['paidLookups'],
                             'paired': {other: paired(grades, name, other, plan) for other in (*peers, *controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'comparisons': comparisons,
            'trajectoryHashes': hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument('--fit', action='store_true')
    phase.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, base, archived, frozen, prior = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, inputs = target(args.cohort, plan, base, archived, frozen, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, _, _ = discovery.training(base)
        report = fit(plan, groups, prior)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
