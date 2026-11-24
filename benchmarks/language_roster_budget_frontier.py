"""Bound the matched-budget value of choosing schedules and challengers."""

import argparse
from collections import Counter
from dataclasses import dataclass
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import bounded_opening_repair_transfer as bounded
from benchmarks.recorded_math_roster_ceiling import extend
from cpo._contract import digest
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.quoted_shared_validation_cycle import _screen as quoted_screen
from cpo.two_sided_certificate_cycle import _run


depth, discovery, adaptive = bounded.depth, bounded.discovery, bounded.adaptive
parent, native, transfer = bounded.parent, bounded.native, bounded.transfer
BOUNDED, ROUTER, RETAIN = bounded.PRIMARY, bounded.ROUTER, adaptive.RETAIN
COMMON, SUBJECT, EPISODE, CYCLE, NOMINEE = 'common', 'by-subject', 'by-episode', 'by-cycle', 'known-nominee'
OLDER_FIT_SHA = '7247f7bd4a866c86ca403e386c3b1e9e8176788c924b3d989cee655a655444f1'
LOCKS = dict(zip(discovery.COHORTS, (
    'fa5d36b2e6f43cd1baf5de7737bfec871d50f0071b3d9bdbf2e23cf672de8b45',
    'f49d442710d8ef88b3de715ae95d6ebf91bf625b76f057b5b1fc3a2e782f3fa2',
    '42ce27fb04c74bee7eba08ed656132db1e475b5b3b8c5b4dc2f7fe4b6abe834a',
    'b702f7ed24e18ad060b914241c46679747debc96b95fa99532d92d8a3d7b33ec',
    'eb550954a9e41fdb0238c04d0180b6c507f1230f5cdd297529c4f363d8a6166d',
    '736a5ea5837186eb08aaaac7e0a422b9615db1a6c69abe020ad84a38417c0ff3',
    '6638d7cd162eab40e561f48d20335264f15733d19c40ef26d5c69b1ddf8519ab',
), strict=True))


@dataclass(frozen=True)
class Point:
    passes: int
    cost: int
    actions: tuple


def prepare(cohort):
    previous, base, archived, frozen, _ = bounded.contract()
    fit = json.loads(transfer.read_locked('docs/bounded-opening-repair-fit-v1.json', OLDER_FIT_SHA))
    inherited, inputs = bounded.target(cohort, previous, base, archived, frozen, fit)
    lock = LOCKS[cohort]
    receipt = json.loads(transfer.read_locked(f'docs/bounded-opening-repair-transfer-{cohort.lower()}-v1.json', lock))
    if digest(inherited) != receipt['planSha256']:
        raise ValueError('The bounded opening replay must reproduce the exact target layout')
    path = Path(__file__).resolve()
    ceiling = transfer.ROOT / 'benchmarks/recorded_math_roster_ceiling.py'
    plan = {**inherited, 'protocol': 'language-roster-budget-frontier-v1', 'boundedTransferSha256': lock,
            'boundedFitSha256': OLDER_FIT_SHA,
            'sourceSha256': {**inherited['sourceSha256'],
                             **{str(file.relative_to(transfer.ROOT)): sha256(file.read_bytes()).hexdigest()
                                for file in (path, ceiling)}},
            'singleCandidateValidationRows': [1, inherited['caseCounts'][1]],
            'scope': 'Pool the same bounded CPO lookup budget across the three-cycle episodes. Compare a single '
                     'fixed setting, a constant setting per subject, one per episode, and independently choosing '
                     'a setting each cycle. Then add hindsight choice of a single roster challenger validated on '
                     'one or all shared validation cases and qualified by the original proof. Replay every '
                     'attaining choice, including both baselines. No target outcomes can enter a live policy.'}
    return plan, (*inputs[:-1], receipt['results'])


def engines(plan, models, static):
    screens = bounded.screens(plan)
    base = [name for name, *_ in plan['controls']]
    fixed = {name: partial(_run, screen=screens[name]) for name in base}
    fixed[BOUNDED] = partial(run_qualification_prefix_cycle,
                             screens=tuple(screens[action] for action in plan['actions'][BOUNDED]))
    fixed[ROUTER] = adaptive.routed_runner(plan, models, static)
    fixed[RETAIN] = None
    singles = {f'candidate/{slot}/{count}': (slot, count)
               for slot in range(plan['challengers']) for count in plan['singleCandidateValidationRows']}
    return fixed, singles


def episode_model(plan, cells, stages, fixed, singles):
    run = native.paired.cycle.execute_path
    cap = max(limit for _, _, _, limit in plan['controls'])
    verify = depth.continuous.routing.verify_qualification
    trace_point = native.paired.reference.point
    held = stages[0][2][-1]

    @cache
    def step(index, incumbent, action):
        if action == RETAIN:
            return incumbent, 0, None
        seed, roster, roles = stages[index]
        if action in singles:
            slot, rows = singles[action]
            roster = roster[slot:slot + 1]
            search = partial(quoted_screen, halve=False)
            runner = partial(_run, screen=lambda base, pool, cases, observe, _: search(
                base, pool, cases, observe, 2 * rows))
        else:
            runner = fixed[action]
        decision, ledger = run(runner, cells, incumbent, roster, roles, seed, cap, 1)
        verify(cells, incumbent, roles, decision, ledger, 1)
        return decision.prompt, len(ledger), (decision, ledger)

    def rollout(start, actions):
        current, spent, path = start, 0, []
        for index, action in enumerate(actions):
            chosen, reads, evidence = step(index, current, action)
            spent += reads
            if evidence is not None:
                _, _, signature = trace_point(cells, held, *evidence)
                path.append((current, chosen, signature))
            current = chosen
        return Point(sum(cells[current][case] for case in held), spent, tuple(actions)), path

    def expand(start, actions):
        states = {start: (0, ())}
        for index in range(len(stages)):
            following = {}
            for incumbent, (cost, path) in states.items():
                for action in actions:
                    candidate, charge, _ = step(index, incumbent, action)
                    point = cost + charge, (*path, action)
                    if point < following.get(candidate, (float('inf'), ())):
                        following[candidate] = point
            states = following
        return [Point(sum(cells[prompt][case] for case in held), cost, path)
                for prompt, (cost, path) in states.items()]

    return rollout, expand, step.cache_clear


def efficient(options):
    points = {}
    for point in options:
        key = point.passes, point.cost
        if key not in points or point.actions < points[key].actions:
            points[key] = point
    return tuple(points[item] for item in extend({0: 0}, points).items())


def pool(menus, budget):
    """Return the least expensive selection maximizing score under one budget."""
    available = {0: 0}
    history = []
    for menu in menus:
        options = efficient(menu)
        history.append((available, options))
        available = {score: cost for score, cost in
                     extend(available, [(point.passes, point.cost) for point in options]).items() if cost <= budget}
    if not available:
        raise ValueError('No complete menu selection fits this budget')
    passes = max(available)
    score, price = passes, available[passes]
    selected = []
    for preceding, options in reversed(history):
        for point in options:
            if preceding.get(score - point.passes) == price - point.cost:
                selected.append(point)
                score -= point.passes
                price -= point.cost
                break
        else:
            raise ValueError('Every frontier point must have a real attainer')
    if score or price:
        raise ValueError('Portfolio reconstruction must settle every pass and lookup')
    return selected[::-1]


def summarize(points):
    return {'holdoutPasses': sum(point.passes for point in points), 'paidLookups': sum(point.cost for point in points)}


def capture(plan, panels, fixed, singles):
    names = (BOUNDED, ROUTER)
    all_cases, episode_menus, cycle_menus, nominee_menus = [], [], [], []
    traces = {}
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        paths = {name: [] for name in names}
        for seed in plan['seeds']:
            start, stages = depth.continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            rollout, expand, clear = episode_model(plan, cells, stages, fixed, singles)
            points = {}
            for action in fixed:
                points[action], trace = rollout(start, (action,) * len(stages))
                if action in paths:
                    paths[action].append(trace)
            episode_menus.append(points)
            cycle_menus.append(efficient(expand(start, tuple(fixed))))
            nominee_menus.append(efficient(expand(start, (*fixed, *singles))))
            clear()
            all_cases.append((subject, model, seed, cells, stages, start))
        traces[f'{subject}/{model}'] = {name: digest(value) for name, value in paths.items()}
    return all_cases, episode_menus, cycle_menus, nominee_menus, traces


def choose_fixed(episodes, menus, actions, budget):
    common_points = {name: summarize([menu[name] for menu in menus]) for name in actions}
    common = native.gepa.best_fixed(common_points, tuple(name for name in actions if name != RETAIN), budget)
    grouped = {}
    for (subject, *_), menu in zip(episodes, menus, strict=True):
        totals = grouped.setdefault(subject, {name: Counter() for name in actions})
        for name, point in menu.items():
            totals[name].update(holdoutPasses=point.passes, paidLookups=point.cost)
    solve = native.paired.frontier.transfer.fitted.prior.by_subject_ceiling
    tuned = solve(grouped, tuple(name for name in actions if name != RETAIN), {SUBJECT: budget})[SUBJECT]
    return {COMMON: [menu[common['setting']] for menu in menus],
            SUBJECT: [menu[tuned['settingsBySubject'][case[0]]] for case, menu in zip(episodes, menus, strict=True)]}


def measure(plan, panels, models, static, gepa, simple, prior):
    fixed, singles = engines(plan, models, static)
    episodes, menus, cycles, nominees, traces = capture(plan, panels, fixed, singles)
    for name in (BOUNDED, ROUTER):
        if (summarize([menu[name] for menu in menus]) != prior['policies'][name]
                or any(values[name] != prior['trajectoryHashes'][panel][name] for panel, values in traces.items())):
            raise ValueError('The original bounded opening and router must reproduce exactly')
    budget = prior['policies'][BOUNDED]['paidLookups']
    chosen = choose_fixed(episodes, menus, fixed, budget)
    chosen.update({EPISODE: pool([menu.values() for menu in menus], budget),
                   CYCLE: pool(cycles, budget), NOMINEE: pool(nominees, budget)})
    results = {}
    for name, points in chosen.items():
        totals = summarize(points)
        if totals['paidLookups'] > budget:
            raise ValueError('Every selected menu must fit the common paid budget')
        paths, counts = [], Counter()
        for point, (subject, model, seed, cells, stages, start) in zip(points, episodes, strict=True):
            rollout, _, clear = episode_model(plan, cells, stages, fixed, singles)
            if rollout(start, point.actions)[0] != point:
                raise ValueError('Every chosen point must reproduce via paid callbacks')
            clear()
            counts.update(point.actions)
            paths.append((subject, model, seed, point.actions))
        results[name] = {**totals, 'selectedActions': dict(counts), 'choicesSha256': digest(paths)}
    scores = [point['holdoutPasses'] for point in results.values()]
    if scores != sorted(scores) or scores[0] < prior['policies'][BOUNDED]['holdoutPasses']:
        raise ValueError('Each expanded menu must contain the previous attainable selections')
    native_bounds, _ = parent.compare_native(plan, panels, gepa, budget,
                                              simple['settingsTotals'][RETAIN]['holdoutPasses'],
                                              {subject: {} for subject in plan['subjects']})
    return {'episodes': len(episodes), 'budget': budget, 'baseline': prior['policies'][BOUNDED],
            'frontiers': results, 'nativeBoundsAtBudget': native_bounds,
            'baselineTrajectoryHashes': traces}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=discovery.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inputs = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    receipt = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
