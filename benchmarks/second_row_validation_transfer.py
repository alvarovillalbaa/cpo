"""Budget an additional validation case after a perfect one-row opening."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import qualification_prefix_depth_transfer as depth
from cpo._contract import digest
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.second_row_validation import screen
from cpo.two_sided_certificate_cycle import _run


discovery, adaptive, parent, transfer, native = depth.discovery, depth.adaptive, depth.parent, depth.transfer, depth.native
BASELINE, ROUTER = depth.ORIGINAL, depth.ROUTED
REPAIR, GUARDED, FITTED = 'second-row-repair', 'second-row-guard', 'fitted-second-row'


def contract():
    inherited, base, archived, frozen = depth.contract()
    original = tuple(inherited['originalDepthActions'])
    if len(set(original[1:])) != 1:
        raise ValueError('The quoted policy must use one common screen after an opening pass')
    settings = {name: (mode, width, cap) for name, mode, width, cap in base['controls']}
    mode, width, cap = settings[original[1]]
    if mode != depth.checkpoint.controls.HALVING or cap != width + 1:
        raise ValueError('The quoted branch must fund exactly one shared row')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/second_row_validation.py')
    plan = {**base, 'protocol': 'second-row-validation-fit-v1', 'originalFitSha256': inherited['originalFitSha256'],
            'baselineActions': original, 'choices': (original[1], REPAIR, GUARDED), 'width': width, 'cap': cap,
            'sourceSha256': {**inherited['sourceSha256'],
                             **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}},
            'scope': 'Keep the original miss-first action. At each later first-miss position select the original '
                     'one-row screen, a second-row repair screen, or a second-row screen requiring the first '
                     'pass to be preserved. Fit all tables on the existing task-disjoint discovery set '
                     'within the original router budgets. No extra qualification probes or bigger search cap.'}
    return plan, base, archived, frozen


def limited(incumbent, candidates, rows, evaluate, cap, *, width, limit, preserve_first):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, limit), preserve_first=preserve_first)


def screens(plan):
    options = discovery.screens_with_quotes(plan)
    options.update({name: partial(limited, width=plan['width'], limit=plan['cap'], preserve_first=name == GUARDED)
                    for name in (REPAIR, GUARDED)})
    return options


def fit(plan, frozen, groups):
    baseline = tuple(plan['baselineActions'])
    menu = [(baseline[0], *tail) for tail in product(plan['choices'], repeat=len(baseline) - 1)]
    engines = {name: partial(_run, screen=action) for name, action in screens(plan).items()}
    points = depth.sweep(plan, groups, menu, engines)
    if points[baseline] != frozen['fitted'][adaptive.ADAPTIVE]['byCohort']:
        raise ValueError('The earlier quoted discovery scores and prices must reproduce')
    budgets = {cohort: point['paidLookups'] for cohort, point in frozen['baseline'].items()}
    selected = adaptive.promotion.choose_actions(points, budgets, False)
    if depth.rank(points[selected]) >= depth.rank(points[baseline]):
        selected = baseline
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'selected': selected,
            'budgets': budgets, 'menu': {'|'.join(table): totals for table, totals in points.items()}}


def target(cohort, plan, base, archived, frozen, fit_receipt):
    if fit_receipt['planSha256'] != digest(plan) or digest(fit_receipt['plan']) != digest(plan):
        raise ValueError('The fitted table must come from the current discovery plan')
    original = tuple(plan['baselineActions'])
    chosen = tuple(fit_receipt['selected'])
    if (len(chosen) != len(original) or chosen[0] != original[0]
            or any(action not in plan['choices'] for action in chosen[1:])):
        raise ValueError('Use a fitted table from the sealed menu')
    prior_plan, panels, models, static, gepa, simple, _, _ = discovery.prepare_target(cohort, base, frozen, archived)
    lock = depth.RECEIPTS[cohort]
    receipt = json.loads(transfer.read_locked(f'docs/quoted-schedule-discovery-transfer-{cohort.lower()}-v1.json', lock))
    if digest(prior_plan) != receipt['planSha256']:
        raise ValueError('The target must preserve the original scored layouts and models')
    actions = {BASELINE: original, FITTED: chosen, REPAIR: (original[0],) + (REPAIR,) * (len(chosen) - 1),
               GUARDED: (original[0],) + (GUARDED,) * (len(chosen) - 1)}
    target_plan = {**prior_plan, 'protocol': 'second-row-validation-transfer-v1',
                   'width': plan['width'], 'cap': plan['cap'], 'fitReceiptSha256': digest(fit_receipt),
                   'originalTransferSha256': lock, 'sourceSha256': {**prior_plan['sourceSha256'], **plan['sourceSha256']},
                   'actions': actions, 'scope': 'Verify the original paid paths and compare the fitted table, '
                                                'both always-enrolled second-row controls and the incumbent router. '
                                                'Reprice the simple menu and native bounds at the new realized costs.'}
    return target_plan, panels, models, static, gepa, simple, receipt['results']


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
                traces[name] != prior['trajectoryHashes'][panel][name] for panel, traces in hashes.items()):
            raise ValueError('Both earlier paid paths must reproduce')
    comparisons = {}
    paired = native.frozen.paired_effects.paired_effect
    for name in (FITTED, REPAIR, GUARDED):
        spend = totals[name]['paidLookups']
        grades = {subject: dict(scores) for subject, scores in vectors.items()}
        controls = parent.compare_simple(plan, panels, simple, spend, grades)
        bounds, attainers = parent.compare_native(plan, panels, gepa, spend,
                                                   simple['settingsTotals'][adaptive.RETAIN]['holdoutPasses'], grades)
        comparisons[name] = {'simpleAtBudget': controls, 'nativeBoundsAtBudget': bounds,
                             'replayedNativeAnchors': attainers, 'withinRouterCost': spend <= totals[ROUTER]['paidLookups'],
                             'paired': {other: paired(grades, name, other, plan)
                                        for other in (BASELINE, ROUTER, *controls, *attainers)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals,
            'trajectoryHashes': hashes, 'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, base, archived, frozen = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, *inputs = target(args.cohort, plan, base, archived, frozen, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, _, _ = discovery.training(base)
        report = fit(plan, frozen, groups)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
