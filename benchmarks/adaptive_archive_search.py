"""Fit a search choice from the first paid qualification reply and test transfer."""

import argparse
from collections import Counter
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import continuous_search_controls as controls
from cpo._contract import digest
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


continuous, promotion = controls.continuous, controls.promotion
native, transfer = continuous.native, continuous.transfer
ROUTED, RETAIN = continuous.PRIMARY, continuous.RETAIN
ADAPTIVE, FIXED = 'adaptive-search', 'fixed-search'
COHORTS = continuous.COHORTS
RECEIPTS = dict(zip(COHORTS, (
    '1139a8008be9ec0a9c8a7d77d46810d06c98c39691053e42a77d25fed85d3eb0',
    '1c0f0bc6077504a663db84d07b6628670e8f6ce5a447063e1cae104897992ed2',
    '199b292738342a3e797b3ce0ab559af02120337db79a9a37011e15afcd99f145',
    '41430317b2c46be4ea85395485054c533d17919c134b1114d55bd21975953376',
    'ee3694eca001093a74138347342440edbf0540e57b2ad060d35a4044d9784f60',
    'ddd0d7e92c0fc41ba3cf297f37887817358ff28475cffbc596d638c81cb777b7',
    'fd6cecc0dccaac39e24cd048118969a027dca09895ed88a164761c5ae0897c27',
), strict=True))


def retain(incumbent, candidates, rows, evaluate, cap):
    return FinalistResult(incumbent, None, 0), None


def limited(screen, limit, incumbent, candidates, rows, evaluate, cap):
    return screen(incumbent, candidates, rows, evaluate, min(cap, limit))


def routed_runner(plan, models, static):
    original = promotion.runner_map(models, static)[ROUTED]

    def run(*args, metric_limit, **kwargs):
        return original(*args, metric_limit=min(metric_limit, plan['fullRosterCap']), **kwargs)

    return run


def screens(plan):
    original = {name: partial(limited, screen, plan['fullRosterCap'])
                for name, screen in continuous.routing.SCREENS.items() if screen is not None}
    alternatives = {name: partial(limited, partial(controls.screen, mode=mode, width=width), cap)
                    for name, mode, width, cap in plan['controls']}
    return {RETAIN: retain, **original, **alternatives}


def cycle(incumbent, candidates, rows, qualification, evaluate, *, metric_limit,
          qualify, minimum_gain, seed, actions):
    """Use the first incumbent qualification grade already needed by the cycle."""
    first = None

    def record(prompt, row, repeat):
        nonlocal first
        grade = qualify(prompt, row, repeat)
        if first is None:
            first = grade
        return grade

    def select(base, roster, panel, observe, cap):
        return actions[int(first)](base, roster, panel, observe, cap)

    return _run(incumbent, candidates, rows, qualification, evaluate, metric_limit=metric_limit,
                qualify=record, minimum_gain=minimum_gain, seed=seed, screen=select)


def training_plan():
    inherited, models, static = promotion.training_plan()
    discovery, groups, *_ = native.prepare()
    targets = {subject for cohort in COHORTS for subject, _, _ in continuous.prepare(cohort)[1]}
    enrollment = {cohort: [(subject, model) for subject, model, _ in panels if subject not in targets]
                  for cohort, panels in groups.items()}
    if not any(enrollment.values()):
        raise ValueError('Discovery requires at least one task absent from all target cohorts')
    plan = {**inherited, 'protocol': 'adaptive-archive-search-fit-v1', 'discoveryPlanSha256': digest(discovery),
            'fitEnrollment': enrollment, 'targetSubjectsExcluded': sorted(targets),
            'controls': list(controls.settings(inherited['caseCounts'][1])),
            'sourceSha256': {**inherited['sourceSha256'], **{Path(path).name: sha256(Path(path).read_bytes()).hexdigest()
                        for path in (__file__, controls.__file__, transfer.ROOT / 'cpo/two_sided_certificate_cycle.py')}},
            'scope': 'Compare every pair of search screens indexed by the first incumbent qualification '
                     'reply, with no added probe. Use identical action tables in all three cycles. Maximize discovery '
                     'passes subject to each discovery cohort’s realized frozen-router budget. Select a control '
                     'with the same action on both branches. Break ties by cost and then by action names. '
                     'Exclude all target task names from discovery and fit before transfer.'}
    plan['actions'] = sorted(screens(plan))
    return plan, groups, models, static


def fit(plan, groups, models, static):
    search = screens(plan)
    runners = {name: partial(_run, screen=screen) for name, screen in search.items()}
    runners[ROUTED] = routed_runner(plan, models, static)
    cap = max(value for _, _, _, value in plan['controls'])
    run = native.paired.cycle.execute_path
    verify = continuous.routing.verify_qualification
    pairs = tuple(product(plan['actions'], repeat=2))
    menu = {pair: {} for pair in pairs}
    baseline = {}
    for cohort, panels in groups.items():
        enrollment = set(map(tuple, plan['fitEnrollment'][cohort]))
        if not enrollment:
            continue
        points = {pair: [0, 0] for pair in pairs}
        baseline[cohort] = Counter()
        for subject, model, matrix in panels:
            if (subject, model) not in enrollment:
                continue
            cells, _ = transfer.case_cells(matrix)
            for seed in plan['seeds']:
                start, cycles = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
                held = cycles[0][2][-1]
                scores = {prompt: sum(cells[prompt][case] for case in held)
                          for prompt in {start, *(prompt for _, roster, _ in cycles for prompt in roster)}}

                @cache
                def transition(index, current, action):
                    local_seed, roster, roles = cycles[index]
                    result, ledger = run(runners[action], cells, current, roster, roles, local_seed, cap, 1)
                    verify(cells, current, roles, result, ledger, 1)
                    if action != ROUTED and next(iter(ledger), None) != ('qualification', current, str(roles[2][0])):
                        raise ValueError('Each fit action must have paid for its routing feature first')
                    return result.prompt, len(ledger)

                for pair, point in points.items():
                    current, cost = start, 0
                    for index, (_, _, roles) in enumerate(cycles):
                        action = pair[int(cells[current][roles[2][0]])]
                        current, paid = transition(index, current, action)
                        cost += paid
                    point[0] += scores[current]
                    point[1] += cost
                current, cost = start, 0
                for index in range(len(cycles)):
                    current, paid = transition(index, current, ROUTED)
                    cost += paid
                baseline[cohort].update(holdoutPasses=scores[current], paidLookups=cost)
                transition.cache_clear()
        for pair, (passed, cost) in points.items():
            menu[pair][cohort] = {'holdoutPasses': passed, 'paidLookups': cost}
    budgets = {cohort: point['paidLookups'] for cohort, point in baseline.items()}
    chosen = {name: promotion.choose_actions(menu, budgets, name == FIXED) for name in (ADAPTIVE, FIXED)}
    return {'plan': plan, 'planSha256': digest(plan), 'baseline': baseline, 'providerRequests': 0,
            'fitted': {name: {'actions': pair, 'byCohort': menu[pair]} for name, pair in chosen.items()},
            'discoveryMenuSha256': digest({'>'.join(pair): totals for pair, totals in menu.items()})}


def prepare_target(cohort, training, trained):
    if trained['planSha256'] != digest(training) or digest(trained['plan']) != digest(training):
        raise ValueError('Transfer requires the current fitted plan')
    base, panels, models, static, _ = controls.prepare(cohort)
    if {subject for subject, _, _ in panels} & {subject for rows in training['fitEnrollment'].values()
                                               for subject, _ in rows}:
        raise ValueError('No target task may appear in discovery')
    lock = RECEIPTS[cohort]
    ref = json.loads(transfer.read_locked(f'docs/continuous-search-controls-{cohort.lower()}-v1.json', lock))
    if ref['planSha256'] != digest(base):
        raise ValueError('The transfer cohort must match the frozen comparator menu')
    gepa = json.loads(transfer.read_locked(
        f'docs/continuous-archive-routing-{cohort.lower()}-v1.json', promotion.RECEIPTS[cohort]))['results']
    plan = {**base, 'protocol': 'adaptive-archive-search-transfer-v1', 'fitSha256': digest(trained),
            'controlReceiptSha256': lock, 'scope': 'Replay frozen discovery choices at the original target layouts. '
                     'Price the full simple menu and native GEPA anchors at the adaptive policy’s realized cost. '
                     'Require a positive paired lower endpoint over the earlier router, fitted fixed and each best common '
                     'alternative, a higher score than both subject-tuned ceilings, and no extra cost over routed CPO.'}
    return plan, panels, models, static, ref['results'], gepa


def replay(plan, panels, runners, schedules, vectors):
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    cap = max(value for _, _, _, value in plan['controls'])
    totals = {name: Counter() for name in schedules}
    hashes = {}
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        scores = vectors.setdefault(subject, {})
        traces = {name: [] for name in schedules}
        for seed in plan['seeds']:
            start, cycles = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            held = cycles[0][2][-1]
            transition = promotion.cached_transitions(cells, cycles, runners, cap)
            for name, schedule in schedules.items():
                action = schedule[subject]
                if action == RETAIN:
                    current, cost, path = start, 0, []
                else:
                    current, cost, path = promotion.rollout(start, len(cycles), (action, action), transition)
                grades = [cells[current][case] for case in held]
                traces[name].append(path)
                totals[name].update(holdoutPasses=sum(grades), paidLookups=cost)
                add(scores.setdefault(name, [0] * len(held)), grades)
            transition.cache_clear()
        hashes[f'{subject}/{model}'] = {name: digest(paths) for name, paths in traces.items()}
    return totals, hashes


def measure(plan, panels, models, static, trained, ref, gepa):
    search = screens(plan)
    runners = {ROUTED: routed_runner(plan, models, static)}
    runners.update({name: partial(cycle, actions=tuple(search[action] for action in trained['fitted'][name]['actions']))
                    for name in (ADAPTIVE, FIXED)})
    subjects = {subject for subject, _, _ in panels}
    vectors = {}
    totals, hashes = replay(plan, panels, runners, {name: dict.fromkeys(subjects, name)
                                                   for name in (ADAPTIVE, FIXED, ROUTED)}, vectors)
    if totals[ROUTED] != ref['cpo'][ROUTED] or any(
            trace[ROUTED] != ref['cpoTrajectoryHashes'][panel][ROUTED] for panel, trace in hashes.items()):
        raise ValueError('The archived router must reproduce every paid trajectory')
    budget = totals[ADAPTIVE]['paidLookups']
    menu = ref['settingsTotals']
    settings = tuple(name for name in menu if name != RETAIN)
    common = {mode: native.gepa.best_fixed(menu, [name for name in settings if name.startswith(f'{mode}/')], budget)
              for mode in controls.MODES}
    ceiling = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    tuned = ceiling(ref['settingsBySubject'], settings, {'adaptive': budget})['adaptive']
    schedules = {name: dict.fromkeys(subjects, point['setting']) for name, point in common.items()}
    schedules['subject-tuned-simple'] = tuned['settingsBySubject']
    simple, _ = replay(plan, panels, {name: partial(_run, screen=search[name]) for name in settings}, schedules, vectors)
    for name, point in {**common, 'subject-tuned-simple': tuned}.items():
        if any(simple[name][key] != point[key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('Every selected simple alternative must attain its reported score and cost')

    retained = menu[RETAIN]['holdoutPasses']
    bounds = {key: promotion.budget_bounds(gepa[key], gepa['cpo'], budget, retained)
              for key in ('bestCommonGepa', 'subjectTunedGepa')}
    anchor = bounds['bestCommonGepa']['attainer']
    setting = anchor['setting'] if anchor else RETAIN
    expected = ({key: anchor[key] for key in ('holdoutPasses', 'paidLookups')} if anchor
                else {'holdoutPasses': retained, 'paidLookups': 0})
    if promotion.compare_native(panels, plan, vectors, {'common-gepa': dict.fromkeys(subjects, setting)}) != {
            'common-gepa': expected}:
        raise ValueError('The affordable native anchor must reproduce its archived score and cost')
    paired = native.frozen.paired_effects.paired_effect
    effects = {name: paired(vectors, ADAPTIVE, name, plan) for name in (FIXED, ROUTED, *schedules, 'common-gepa')}
    upper = bounds['subjectTunedGepa']['upperPasses']
    gate = (budget <= totals[ROUTED]['paidLookups']
            and all(effects[name]['pairedRange95'][0] > 0 for name in (FIXED, ROUTED, *common, 'common-gepa'))
            and effects['subject-tuned-simple']['holdoutPassDifference'] > 0
            and bounds['bestCommonGepa']['upperPasses'] == bounds['bestCommonGepa']['lowerPasses']
            and upper is not None and totals[ADAPTIVE]['holdoutPasses'] > upper)
    return {'policies': totals, 'trajectoryHashes': hashes, 'commonSimple': common, 'subjectTunedSimple': tuned,
            'gepaBounds': bounds, 'pairedAdaptive': effects, 'gatePassed': gate}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--fit', type=Path)
    modes.add_argument('--cohort', choices=COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    training, groups, models, static = training_plan()
    if version('gepa') != training['gepaVersion']:
        parser.error('Replay requires pinned GEPA')
    if args.fit is not None:
        if args.fit.exists() or any((args.fitted, args.execute, args.out)):
            parser.error('Fit requires only a fresh output path')
        result, out = fit(training, groups, models, static), args.fit
    else:
        if args.fitted is None:
            parser.error('Transfer requires a fitted receipt')
        trained = json.loads(args.fitted.read_bytes())
        plan, *inputs = prepare_target(args.cohort, training, trained)
        seal = digest(plan)
        if args.execute is None and args.out is None:
            print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
            return
        if args.execute != seal or args.out is None or args.out.exists():
            parser.error('Transfer requires the current seal and a fresh output path')
        panels, models, static, ref, gepa = inputs
        result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
                  'results': measure(plan, panels, models, static, trained, ref, gepa)}
        out = args.out
    with out.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
