"""Compare stronger qualification for a repair found after a case switch."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import interleaved_validation_transfer as previous
from cpo._contract import digest
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.second_case_qualification import GUARDS, NO_LOSS, TWO_GAIN, run_second_case_qualification_cycle


switch, discovery, adaptive = previous.switch, previous.discovery, previous.adaptive
depth, parent, native, transfer = previous.depth, previous.parent, previous.native, previous.transfer
BOUNDED, SWITCH, ROUTER = previous.BOUNDED, previous.SWITCH, previous.ROUTER
FIT_SHA = '712d89f4d396e59c5e1e95f550225f3653eb6c112e7f6c5abb6ff45846debee6'
LOCKS = dict(zip(discovery.COHORTS, (
    '9b77fde0693b841117cf78b87554987a77d6cb655791b1085b8eea008e33bf30',
    '17c21894cbb090d159cd18f9afbaad1c220ade2c136a6958fdb0953e048bfb9e',
    '1e149f6ded34025185d000823e0b7a34036aa7b47417e80fe253f80912e7d63c',
    '4963c4f5f634f83a6fcbc40b222ef11b588ff30fba1bf228505fa7fb62de178b',
    'c6248fd5e46ece6a7b7344f813d611db7871d33da7dd5f81f63a2c6aa8182ae9',
    'b48f57441244dc58c6af77bf000c1e5409012413ece8729ea173bf1150f755b6',
    '97e32ef7301a45c8ca02e4e06e9752c69ee820d03b1985dbb7e513b4c57c85bb',
), strict=True))


def contract():
    inherited, switch_context, switch_fit = previous.contract()
    old_fit = json.loads(transfer.read_locked('docs/interleaved-validation-fit-v1.json', FIT_SHA))
    if digest(inherited) != old_fit['planSha256'] or digest(old_fit['plan']) != old_fit['planSha256']:
        raise ValueError('The previous discovery plan must reproduce')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/second_case_qualification.py', root / 'cpo/paired_qualification.py')
    plan = {**inherited, 'protocol': 'second-case-qualification-fit-v1', 'interleavedFitSha256': FIT_SHA,
            'qualificationGuards': GUARDS, 'sourceSha256': {**inherited['sourceSha256'],
                                                           **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest()
                                                              for file in files}},
            'scope': 'Keep the fixed switch after two and strengthen only an ordinarily promoted second-case '
                     'nominee. Compare a two-pass net gain with preserving every incumbent qualification pass. '
                     'Use the original cap and charge only unread grades. Fit one policy within the original '
                     'per-cohort discovery router budgets, preserving every task and case boundary.'}
    return plan, inherited, switch_context, switch_fit, old_fit


def runners(plan):
    choices = switch.screens(plan)
    bounded = plan['boundedActions']
    opening, changed = choices[bounded[0]], choices[plan['fixedSwitchAction']]
    stock = {BOUNDED: tuple(choices[action] for action in bounded),
             SWITCH: (opening,) + (changed,) * (len(bounded) - 1)}
    return {**{name: partial(run_qualification_prefix_cycle, screens=screens) for name, screens in stock.items()},
            **{guard: partial(run_second_case_qualification_cycle, opening_screen=opening,
                              switch_screen=changed, guard=guard) for guard in GUARDS}}


def audit_gate(cells, incumbent, roles, result, ledger, guard):
    nominee = result.search.finalist
    if nominee is None:
        if result.prompt != incumbent:
            raise ValueError('Deployment requires a nominated challenger')
        return {}
    rows = roles[2]
    if guard not in GUARDS + (SWITCH,):
        depth.continuous.routing.verify_qualification(cells, incumbent, roles, result, ledger, 1)
        return {}
    second = str(roles[1][1])
    second_repair = (ledger.get(('qualification', incumbent, str(rows[0]))) is True
                     and ledger.get(('validation', incumbent, second)) is False
                     and ledger.get(('validation', nominee, second)) is True)
    differences = [cells[nominee][row] - cells[incumbent][row] for row in rows]
    gain = sum(differences)
    clears = gain >= 1
    promote = clears
    if second_repair and guard == TWO_GAIN:
        promote = gain >= 2
    if second_repair and guard == NO_LOSS:
        promote = clears and min(differences) >= 0
    if result.prompt != (nominee if promote else incumbent):
        raise ValueError('The certificate must match the fully observed independent gate')
    return {'nominees': int(second_repair), 'ordinaryPasses': int(second_repair and clears),
            'promoted': int(second_repair and promote)}


def measure(plan, panels, policies, vectors):
    continuous = depth.continuous
    run = native.paired.cycle.execute_path
    trace_point = native.paired.reference.point
    cap = max(value for _, _, _, value in plan['controls'])
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    totals = {name: Counter() for name in policies}
    diagnostics = {name: Counter() for name in policies}
    hashes = {}
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        grades = vectors.setdefault(subject, {})
        paths = {name: [] for name in policies}
        for seed in plan['seeds']:
            start, stages = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            held = stages[0][2][-1]
            for name, runner in policies.items():
                current, trace, spend = start, [], 0
                for local_seed, roster, roles in stages:
                    decision, ledger = run(runner, cells, current, roster, roles, local_seed, cap, 1)
                    diagnostics[name].update(audit_gate(cells, current, roles, decision, ledger, name))
                    _, _, signature = trace_point(cells, held, decision, ledger)
                    trace.append((current, decision.prompt, signature))
                    spend += len(ledger)
                    current = decision.prompt
                replies = [cells[current][case] for case in held]
                add(grades.setdefault(name, [0] * len(held)), replies)
                totals[name].update(holdoutPasses=sum(replies), paidLookups=spend)
                paths[name].append(trace)
        hashes[f'{subject}/{model}'] = {name: digest(paths) for name, paths in paths.items()}
    return totals, hashes, diagnostics


def fit(plan, groups, prior):
    points = {name: {} for name in (BOUNDED, SWITCH, *GUARDS)}
    policies = runners(plan)
    for cohort, panels in groups.items():
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        if not enrolled:
            continue
        totals, _, _ = measure(plan, [panel for panel in panels if panel[:2] in enrolled], policies, {})
        for name, value in totals.items():
            points[name][cohort] = value
    if points[BOUNDED] != prior['boundedOpening'] or points[SWITCH] != prior['fixedSwitch']:
        raise ValueError('Both previous discovery policies must reproduce exactly')
    budgets = prior['policies'][switch.FITTED]['budgets']
    feasible = [name for name, point in points.items()
                if all(row['paidLookups'] <= budgets[cohort] for cohort, row in point.items())]
    selected = min(feasible, key=lambda arm: (depth.rank(points[arm]), arm != BOUNDED, arm))
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'selected': selected,
            'byPolicy': points, 'budgets': budgets, 'feasible': feasible}


def target(cohort, plan, inherited, switch_context, switch_fit, old_fit, fit_receipt):
    if fit_receipt['planSha256'] != digest(plan) or digest(fit_receipt['plan']) != digest(plan):
        raise ValueError('Target replay requires the sealed fit')
    if fit_receipt['selected'] not in (BOUNDED, SWITCH, *GUARDS):
        raise ValueError('Select from the frozen qualification policies')
    old_plan, data = previous.target(cohort, inherited, switch_context, switch_fit, old_fit)
    lock = LOCKS[cohort]
    prior = json.loads(transfer.read_locked(f'docs/interleaved-validation-transfer-{cohort.lower()}-v1.json', lock))
    if prior['planSha256'] != digest(old_plan):
        raise ValueError('The previous attribution replay must reproduce')
    target_plan = {**old_plan, 'protocol': 'second-case-qualification-transfer-v1', 'fitSha256': digest(fit_receipt),
                   'boundedActions': plan['boundedActions'], 'fixedSwitchAction': plan['fixedSwitchAction'],
                   'qualificationGuards': GUARDS, 'sourceSha256': {**old_plan['sourceSha256'], **plan['sourceSha256']},
                   'priorTransferSha256': lock, 'selectedPolicy': fit_receipt['selected'],
                   'scope': 'Reproduce baseline trajectories and compare two stronger independent '
                            'qualification rules at their actual cost. Verify both decisions against the '
                            'complete qualification panel without using holdout grades for any choice.'}
    return target_plan, (*data[:-1], prior['results'])


def replay(plan, panels, models, static, gepa, simple, prior):
    policies = {**runners(plan), ROUTER: adaptive.routed_runner(plan, models, static)}
    grades = {}
    totals, hashes, diagnostics = measure(plan, panels, policies, grades)
    for name in (BOUNDED, SWITCH, ROUTER):
        if totals[name] != prior['policies'][name] or any(
                trace[name] != prior['trajectoryHashes'][panel][name] for panel, trace in hashes.items()):
            raise ValueError('All three prior paid paths must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name in GUARDS:
        vectors = {subject: dict(values) for subject, values in grades.items()}
        spend = totals[name]['paidLookups']
        controls = parent.compare_simple(plan, panels, simple, spend, vectors)
        bounds, anchors = parent.compare_native(plan, panels, gepa, spend,
                                                 simple['settingsTotals'][adaptive.RETAIN]['holdoutPasses'], vectors)
        comparisons[name] = {'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors, 'simpleAtBudget': controls,
                             'withinRouterCost': spend <= totals[ROUTER]['paidLookups'],
                             'paired': {other: paired(vectors, name, other, plan)
                                        for other in (BOUNDED, SWITCH, ROUTER, *controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'trajectoryHashes': hashes,
            'secondCaseNomineeDiagnostics': diagnostics, 'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inherited, context, switch_fit, old_fit = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        receipt = json.loads(args.fitted.read_bytes())
        plan, inputs = target(args.cohort, plan, inherited, context, switch_fit, old_fit, receipt)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, _, _ = discovery.training(context[2])
        report = fit(plan, groups, switch_fit)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
