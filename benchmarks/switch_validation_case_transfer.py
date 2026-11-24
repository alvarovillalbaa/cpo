"""Test switching from a repeatedly failed validation case at the original cap."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import bounded_opening_repair_transfer as bounded
from cpo._contract import digest
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.switch_validation_case import screen
from cpo.two_sided_certificate_cycle import _run


depth, discovery, adaptive = bounded.depth, bounded.discovery, bounded.adaptive
parent, native, transfer = bounded.parent, bounded.native, bounded.transfer
BOUNDED, ORIGINAL, ROUTER = bounded.PRIMARY, bounded.BASELINE, bounded.ROUTER
FITTED, SAME_COST, FIXED = 'fitted-switch', 'fitted-switch-at-bounded-cost', 'switch-after-two'
FIT_PATH = 'docs/bounded-opening-repair-fit-v1.json'
FIT_SHA = '7247f7bd4a866c86ca403e386c3b1e9e8176788c924b3d989cee655a655444f1'
LOCKS = dict(zip(discovery.COHORTS, (
    'fa5d36b2e6f43cd1baf5de7737bfec871d50f0071b3d9bdbf2e23cf672de8b45',
    'f49d442710d8ef88b3de715ae95d6ebf91bf625b76f057b5b1fc3a2e782f3fa2',
    '42ce27fb04c74bee7eba08ed656132db1e475b5b3b8c5b4dc2f7fe4b6abe834a',
    'b702f7ed24e18ad060b914241c46679747debc96b95fa99532d92d8a3d7b33ec',
    'eb550954a9e41fdb0238c04d0180b6c507f1230f5cdd297529c4f363d8a6166d',
    '736a5ea5837186eb08aaaac7e0a422b9615db1a6c69abe020ad84a38417c0ff3',
    '6638d7cd162eab40e561f48d20335264f15733d19c40ef26d5c69b1ddf8519ab',
), strict=True))


def contract():
    previous, base, archived, frozen, _ = bounded.contract()
    prior = json.loads(transfer.read_locked(FIT_PATH, FIT_SHA))
    if digest(previous) != prior['planSha256'] or digest(prior['plan']) != prior['planSha256']:
        raise ValueError('The bounded opening discovery plan must reproduce')
    original = tuple(prior['selected'])
    controls = tuple(dict.fromkeys((*previous['baselineActions'][1:], *original[1:])))
    switches = {f'switch-{order}/{count}': (count, order == 'unopened')
                for order in ('unopened', 'original') for count in (2, 4, 6)}
    root = transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/switch_validation_case.py')
    plan = {**previous, 'protocol': 'switch-validation-case-fit-v1', 'boundedFitSha256': FIT_SHA,
            'boundedActions': original, 'fixedSwitchAction': 'switch-unopened/2',
            'choices': (*controls, *switches), 'switches': switches,
            'sourceSha256': {**previous['sourceSha256'],
                             **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}},
            'scope': 'Keep the first-qualification-miss action. Try switching after 2, 4 or 6 unsuccessful '
                     'challengers. Try original order and unopened-first order on the second case. Fit on the '
                     'original task-disjoint discovery groups under router caps and separately under the '
                     'bounded opening policy’s actual spend. Keep the existing per-cycle cap and qualification.'}
    return plan, previous, base, archived, frozen, prior


def limited(incumbent, candidates, rows, evaluate, cap, *, width, maximum, initial_probes, unopened_first):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, maximum),
                  initial_probes=initial_probes, unopened_first=unopened_first)


def screens(plan):
    choices = bounded.screens(plan)
    choices.update({name: partial(limited, width=plan['width'], maximum=plan['cap'],
                                    initial_probes=count, unopened_first=unopened)
                    for name, (count, unopened) in plan['switches'].items()})
    return choices


def fit(plan, groups, prior):
    reference = tuple(plan['boundedActions'])
    menu = [(reference[0], *tail) for tail in product(plan['choices'], repeat=len(reference) - 1)]
    engines = {name: partial(_run, screen=action) for name, action in screens(plan).items()}
    points = depth.sweep(plan, groups, menu, engines)
    old = prior['policies'][BOUNDED]
    if points[reference] != old['byCohort'] or points[tuple(plan['baselineActions'])] != prior['original']:
        raise ValueError('Both previous discovery scores and prices must reproduce')
    matched = {cohort: point['paidLookups'] for cohort, point in points[reference].items()}
    policies = {FITTED: bounded.choose(points, old['budgets'], reference),
                SAME_COST: bounded.choose(points, matched, reference)}
    fixed = (reference[0],) + (plan['fixedSwitchAction'],) * (len(reference) - 1)
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'policies': policies,
            'boundedOpening': old['byCohort'], 'fixedSwitch': points[fixed], 'evaluatedTables': len(points),
            'menuSha256': digest({'|'.join(table): totals for table, totals in points.items()})}


def target(cohort, plan, previous, base, archived, frozen, prior, fit_receipt):
    if fit_receipt['planSha256'] != digest(plan) or digest(fit_receipt['plan']) != digest(plan):
        raise ValueError('The fitted schedule must come from the current discovery plan')
    inherited, inputs = bounded.target(cohort, previous, base, archived, frozen, prior)
    lock = LOCKS[cohort]
    verified = json.loads(transfer.read_locked(f'docs/bounded-opening-repair-transfer-{cohort.lower()}-v1.json', lock))
    if digest(inherited) != verified['planSha256']:
        raise ValueError('The bounded replay must reproduce the earlier target plan')
    incumbent = inherited['actions'][BOUNDED]
    fixed = (incumbent[0],) + (plan['fixedSwitchAction'],) * (len(incumbent) - 1)
    actions = {BOUNDED: incumbent, ORIGINAL: inherited['actions'][ORIGINAL], FIXED: fixed}
    for name in (FITTED, SAME_COST):
        table = fit_receipt['policies'][name]['actions']
        if len(table) != len(incumbent) or table[0] != incumbent[0] or set(table[1:]) - set(plan['choices']):
            raise ValueError('Choose only from the sealed discovery menu')
        actions[name] = table
    target_plan = {**inherited, 'protocol': 'switch-validation-case-transfer-v1', 'actions': actions,
                   'fitReceiptSha256': digest(fit_receipt), 'boundedTransferSha256': lock, 'switches': plan['switches'],
                   'sourceSha256': {**inherited['sourceSha256'], **plan['sourceSha256']},
                   'scope': 'Compare both fitted schedules and the fixed switch with the bounded opening, '
                            'original quoted prefix, and router. Price controls at actual spend and '
                            'verify the previous baselines’ paid paths.'}
    return target_plan, (*inputs[:-1], verified['results'])


def replay(plan, panels, models, static, gepa, simple, previous):
    options = screens(plan)
    runners = {name: partial(run_qualification_prefix_cycle, screens=tuple(options[action] for action in table))
               for name, table in plan['actions'].items()}
    runners[ROUTER] = adaptive.routed_runner(plan, models, static)
    schedules = {name: dict.fromkeys(plan['subjects'], name) for name in runners}
    scores = {}
    totals, hashes = adaptive.replay(plan, panels, runners, schedules, scores)
    for name in (BOUNDED, ORIGINAL, ROUTER):
        if totals[name] != previous['policies'][name] or any(
                trace[name] != previous['trajectoryHashes'][panel][name] for panel, trace in hashes.items()):
            raise ValueError('Every earlier baseline score, price and paid path must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name in (FITTED, SAME_COST, FIXED):
        spend = totals[name]['paidLookups']
        vectors = {subject: dict(values) for subject, values in scores.items()}
        controls = parent.compare_simple(plan, panels, simple, spend, vectors)
        bounds, attainers = parent.compare_native(plan, panels, gepa, spend,
                                                   simple['settingsTotals'][adaptive.RETAIN]['holdoutPasses'], vectors)
        comparisons[name] = {'nativeBoundsAtBudget': bounds, 'nativeAnchors': attainers,
                             'simpleAtBudget': controls, 'withinRouterCost': spend <= totals[ROUTER]['paidLookups'],
                             'paired': {other: paired(vectors, name, other, plan)
                                        for other in (BOUNDED, ORIGINAL, ROUTER, *controls, *attainers)}}
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
    plan, previous, base, archived, frozen, prior = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        fitted = json.loads(args.fitted.read_bytes())
        plan, inputs = target(args.cohort, plan, previous, base, archived, frozen, prior, fitted)
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
