"""Fit an incumbent-history routing rule on three-cycle discovery episodes."""

import argparse
from collections import Counter
from functools import cache
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import continuous_archive_routing as previous
from cpo._contract import digest


transfer, native = previous.transfer, previous.native
STATIC, ROUTED = previous.STATIC, previous.PRIMARY
FIXED, SWITCH = 'fitted-fixed-screen', 'fitted-promotion-switch'
MATCHED = 'fixed-budget-switch'
ACTIONS = (STATIC, *previous.previous.OPTIMIZED.values())
PROTOCOLS = (FIXED, SWITCH)
COHORTS = previous.COHORTS
DISCOVERY_BUDGET_PERCENT = 100
RECEIPTS = dict(zip(COHORTS, (
    '4650f552a03869d793a173590f3689e66bdc336d86d4232c410d245feb5d2a39',
    '989763fe86cb86a91968ca33efe74fbb50befca3d1523015a4f7150542ee4de7',
    '5d7b31ae3dea67b6df4c418049fff819c5cd757f9ec1a471d2b210f103c9af34',
    'c4923fe4f44f1eae7919dbc37e39455030ea112219deb1b259b8f3ac16e880ea',
    'ce2d624eef2dd7c39d486d586f5f47fbf277b41f64b5ed5190a3cf63bde5361e',
    '3a5aa3b602255f438a3de3a0b9bdcb710bd80cff47fb811816e574f9957fa80f',
    'b7c97713d2196da7a0ef7acc725b58a684a79111f3052dc3a6e332ec1a25d6f4',
), strict=True))


def rollout(start, cycles, pair, transition):
    current, paid, promoted, receipt = start, 0, False, []
    for index in range(cycles):
        action = pair[1] if promoted else pair[0]
        deployed, cost, trace = transition(index, current, action)
        receipt.append((current, deployed, trace))
        paid += cost
        promoted |= current != deployed
        current = deployed
    return current, paid, receipt


def runner_map(models, static):
    _, compact = previous.previous.make_runners(models, static)
    routing = previous.routing
    return {STATIC: routing.fitted_runner(STATIC, {STATIC: static}, Counter()), **compact}


def cached_transitions(cells, cycles, runners, limit):
    run = native.paired.cycle.execute_path
    point = native.paired.reference.point

    @cache
    def transition(index, current, action):
        seed, roster, roles = cycles[index]
        result, ledger = run(runners[action], cells, current, roster, roles, seed, limit, 1)
        previous.routing.verify_qualification(cells, current, roles, result, ledger, 1)
        measured, _, trace = point(cells, roles[-1], result, ledger)
        return result.prompt, measured['paidLookups'], trace

    return transition


def training_plan():
    short = previous.previous
    inherited, discovery, pooled = short.previous.training_plan()
    fit = short.previous.read_json(short.FIT, short.FIT_SHA)
    if fit['planSha256'] != digest(inherited) or digest(fit['plan']) != fit['planSha256']:
        raise ValueError('The candidate screens must come from the original fits')
    models = {short.previous.POOLED: pooled['models'][short.previous.POOLED], **fit['models']}
    static = pooled['models'][STATIC]
    plan = {**{key: inherited[key] for key in ('caseCounts', 'challengers', 'seeds', 'fullRosterCap', 'gepaVersion')},
            'protocol': 'promotion-aware-archive-routing-fit-v1', 'cycles': previous.CYCLES,
            'discoveryReceiptSha256': transfer.DISCOVERY_SHA, 'screenFitSha256': short.FIT_SHA,
            'sourceSha256': {Path(path).name: sha256(Path(path).read_bytes()).hexdigest()
                             for path in (__file__, previous.__file__, short.__file__, previous.routing.__file__)},
            'actions': ACTIONS, 'budgetPercent': DISCOVERY_BUDGET_PERCENT,
            'scope': 'Evaluate every pair of existing screen actions on discovery. Use the first action until '
                     'the episode’s first verified promotion and the second thereafter. Fit one pair across '
                     'cohorts with the static lookup cap per discovery cohort. Maximize total passes, '
                     'minimize total cost on score ties and use name order for exact ties. Fit the same-action '
                     'control under identical constraints. Report feasibility at 95 percent of each static '
                     'cap. As a secondary analysis select the best distinct-action pair within the fitted '
                     'fixed policy’s actual lookup count in every discovery cohort. Target scores are '
                     'excluded from fitting.'}
    return plan, models, static


def choose_actions(totals, budgets, require_same):
    ranked = []
    for pair, points in totals.items():
        if require_same and pair[0] != pair[1]:
            continue
        if any(point['paidLookups'] > budgets[cohort] for cohort, point in points.items()):
            continue
        ranked.append((-sum(point['holdoutPasses'] for point in points.values()),
                       sum(point['paidLookups'] for point in points.values()), pair))
    if not ranked:
        raise ValueError('No discovery action schedule fits the frozen per-cohort caps')
    return min(ranked)[2]


def fit(plan, models, static):
    _, groups, *_ = native.prepare()
    runners = runner_map(models, static)
    options = {pair: {} for pair in product(ACTIONS, repeat=2)}
    excluded, enrollment = {}, {}
    minimum = plan['cycles'] * sum(plan['caseCounts'])
    for cohort, panels in groups.items():
        too_small = {subject for subject, _, matrix in panels if len(matrix[0]) - len(
            transfer.layouts.source.holdout(subject, len(matrix[0]))) < minimum}
        excluded[cohort] = sorted(too_small)
        enrollment[cohort] = []
        for subject, model, matrix in panels:
            if subject in too_small:
                continue
            enrollment[cohort].append(f'{subject}/{model}')
            cells, _ = transfer.case_cells(matrix)
            for seed in plan['seeds']:
                start, cycles = previous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
                held = cycles[0][2][-1]
                transition = cached_transitions(cells, cycles, runners, plan['fullRosterCap'])
                for pair, points in options.items():
                    deployed, cost, _ = rollout(start, len(cycles), pair, transition)
                    points.setdefault(cohort, Counter()).update(holdoutPasses=sum(cells[deployed][case] for case in held),
                                                                 paidLookups=cost)
                transition.cache_clear()
        if not enrollment[cohort]:
            raise ValueError('The fit requires every discovery cohort to have a funded case layout')
    original = options[STATIC, STATIC]
    budgets = {cohort: point['paidLookups'] * plan['budgetPercent'] // 100 for cohort, point in original.items()}
    tighter = {cohort: point['paidLookups'] * 95 // 100 for cohort, point in original.items()}
    feasible = [pair for pair, points in options.items()
                if all(point['paidLookups'] <= tighter[cohort] for cohort, point in points.items())]
    chosen = {name: choose_actions(options, budgets, name == FIXED) for name in PROTOCOLS}
    matched_budget = {cohort: point['paidLookups'] for cohort, point in options[chosen[FIXED]].items()}
    candidates = {pair: points for pair, points in options.items() if pair[0] != pair[1]}
    chosen[MATCHED] = choose_actions(candidates, matched_budget, False)
    return {'plan': plan, 'planSha256': digest(plan), 'fitted': {name: {'actions': pair, 'byCohort': options[pair]}
                                                              for name, pair in chosen.items()},
            'budgets': budgets, 'realizedFixedBudgets': matched_budget, 'static': original,
            'discoveryPanels': enrollment, 'excludedTasks': excluded,
            'options': {'|'.join(pair): points for pair, points in options.items()},
            'feasibleAt95Percent': {FIXED: sum(left == right for left, right in feasible), SWITCH: len(feasible)}}


def budget_bounds(menu, original_cpo, budget, retained):
    feasible = [name for name, point in menu.items() if point['paidLookups'] <= budget]
    selected = min(feasible, key=lambda name: (-menu[name]['holdoutPasses'], menu[name]['paidLookups'], name), default=None)
    attainer = menu[selected] if selected is not None and menu[selected]['holdoutPasses'] >= retained else None
    upper = [point['holdoutPasses'] for name, point in menu.items() if original_cpo[name]['paidLookups'] >= budget]
    lower = retained if attainer is None else attainer['holdoutPasses']
    bound = min(upper, default=None)
    if bound is not None and lower > bound:
        raise ValueError('A published feasible score cannot exceed the upper budget bound')
    return {'lowerPasses': lower, 'upperPasses': bound, 'attainer': attainer}


def compare_native(panels, plan, vectors, subject_schedules):
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    totals = {name: Counter() for name in subject_schedules}
    for subject, _, matrix in panels:
        _, packed = transfer.case_cells(matrix)
        for seed in plan['seeds']:
            start, stages = previous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            for name, schedule in subject_schedules.items():
                current, cost = start, 0
                for local_seed, roster, roles in stages:
                    current, grades, spent = previous.attaining_trial(schedule[subject],
                                                                       (packed, current, roster, roles, local_seed))
                    cost += spent
                totals[name].update(holdoutPasses=sum(grades), paidLookups=cost)
                add(vectors[subject].setdefault(name, [0] * len(grades)), grades)
    return totals


def prepare(cohort, trained):
    plan, panels, models, static, _ = previous.prepare(cohort)
    ref = json.loads(transfer.read_locked(f'docs/continuous-archive-routing-{cohort.lower()}-v1.json', RECEIPTS[cohort]))
    if ref['planSha256'] != digest(plan):
        raise ValueError('Preserve the exact three-cycle layout and original controls')
    return {**plan, 'protocol': 'promotion-aware-archive-routing-transfer-v1', 'fitSha256': digest(trained),
            'parentReceiptSha256': RECEIPTS[cohort],
            'scope': 'Use frozen discovery actions and verify all original three-cycle CPO trajectories. Price '
                     'the fitted static and promotion-conditioned strategies. Use monotone exact native anchors '
                     'for comparator bounds and directly reproduce the affordable paired controls.',
            'gate': 'Use no more lookups than fitted fixed, beat it and affordable common GEPA at a positive paired '
                    'lower endpoint, exactly identify the affordable common GEPA score, and beat the native '
                    'subject-tuned upper bound.'}, panels, models, static, ref['results']


def measure(plan, panels, models, static, trained, reference):
    runners = runner_map(models, static)
    policies = {name: (name, name) for name in runners}
    policies.update({name: tuple(item['actions']) for name, item in trained['fitted'].items()})
    totals, hashes, vectors = {name: Counter() for name in policies}, {}, {}
    reserve = 0
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        trace = {method: [] for method in policies}
        scores = vectors.setdefault(subject, {})
        for seed in plan['seeds']:
            start, stages = previous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            held = stages[0][2][-1]
            reserve += sum(cells[start][case] for case in held)
            transition = cached_transitions(cells, stages, runners, plan['fullRosterCap'])
            for method, pair in policies.items():
                prompt, cost, path = rollout(start, len(stages), pair, transition)
                grades = [cells[prompt][case] for case in held]
                totals[method].update(holdoutPasses=sum(grades), paidLookups=cost)
                trace[method].append(path)
                add(scores.setdefault(method, [0] * len(grades)), grades)
            transition.cache_clear()
        panel = f'{subject}/{model}'
        hashes[panel] = {method: digest(paths) for method, paths in trace.items()}
        if any(hashes[panel][method] != reference['panelTrajectoryHashes'][panel][method] for method in runners):
            raise ValueError('All frozen continuous CPO paths must reproduce')
    for method in runners:
        if any(totals[method][key] != reference['cpo'][method][key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('Original continuous scores and costs must match')

    budgets = {name: {key: budget_bounds(reference[key], reference['cpo'], totals[name]['paidLookups'], reserve)
                      for key in ('bestCommonGepa', 'subjectTunedGepa')} for name in (*PROTOCOLS, MATCHED)}
    schedule = {}
    expected = {}
    for key, point in budgets[SWITCH].items():
        choice = point['attainer']
        if choice is None:
            schedule[key] = dict.fromkeys(vectors, transfer.RETAIN)
            expected[key] = {'holdoutPasses': reserve, 'paidLookups': 0}
        else:
            schedule[key] = (dict.fromkeys(vectors, choice['setting']) if key == 'bestCommonGepa'
                             else choice['settingsBySubject'])
            expected[key] = {field: choice[field] for field in ('holdoutPasses', 'paidLookups')}
    if compare_native(panels, plan, vectors, schedule) != expected:
        raise ValueError('Every selected native anchor must attain the published three-cycle score and cost')
    paired = native.frozen.paired_effects.paired_effect
    effects = {name: paired(vectors, SWITCH, name, plan) for name in (FIXED, ROUTED, *schedule)}
    common = budgets[SWITCH]['bestCommonGepa']
    ceiling = budgets[SWITCH]['subjectTunedGepa']['upperPasses']
    passed = (totals[SWITCH]['paidLookups'] <= totals[FIXED]['paidLookups'] and effects[FIXED]['pairedRange95'][0] > 0
              and common['lowerPasses'] == common['upperPasses'] and effects['bestCommonGepa']['pairedRange95'][0] > 0
              and ceiling is not None and totals[SWITCH]['holdoutPasses'] > ceiling)
    return {'cpo': totals, 'gepaBounds': budgets, 'pairedSwitch': effects, 'primaryGatePassed': passed,
            'fixedBudgetSwitchAgainstFixed': paired(vectors, MATCHED, FIXED, plan),
            'trajectories': hashes, 'nativeAttainers': expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit', type=Path)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--cohort', choices=COHORTS)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    frozen, candidate_models, candidate_static = training_plan()
    if args.fit is not None:
        if any((args.fitted, args.cohort, args.execute, args.out)) or args.fit.exists():
            parser.error('Fitting requires a fresh path and no transfer arguments')
        document = fit(frozen, candidate_models, candidate_static)
        output = args.fit
    else:
        if args.fitted is None or args.cohort is None:
            parser.error('Transfer requires a frozen fit and a cohort')
        trained = json.loads(args.fitted.read_bytes())
        if trained['planSha256'] != digest(frozen) or digest(trained['plan']) != digest(frozen):
            parser.error('Use the exact discovery source and fit')
        plan, panels, models, static, reference = prepare(args.cohort, trained)
        seal = digest(plan)
        if args.execute is None and args.out is None:
            print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
            return
        if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
            parser.error('Replay requires the current seal, a fresh path and pinned GEPA')
        document = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
                    'results': measure(plan, panels, models, static, trained, reference)}
        output = args.out
    with output.open('x') as out:
        json.dump(document, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
