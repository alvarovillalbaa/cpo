"""Fit a paid first-miss position refinement on separate discovery tasks."""

import argparse
from collections import Counter
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import quoted_schedule_checkpoint_transfer as checkpoint
from cpo._contract import digest
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.two_sided_certificate_cycle import _run


discovery, parent = checkpoint.discovery, checkpoint.parent
adaptive, native, transfer = checkpoint.adaptive, checkpoint.native, checkpoint.transfer
continuous, ROUTED = checkpoint.continuous, checkpoint.ROUTED
ORIGINAL, DEPTH = 'quoted-prefix', 'qualification-prefix-depth'
RECEIPTS = dict(zip(discovery.COHORTS, (
    '96c2eedf04e5cd490e6572b706efa62810a99fdea45ba049c93596a702f8eff8',
    'd2e5e054f7d02b44bdb43d9855fd94dc1326ac60a88eddf45c48d9f51dc3fe9b',
    '323325483ce2148fcb82a00574d158d714073011c182398e9b5d033d2266507f',
    '4c00b6a5267ab961f79bf9b4338ffbdd030251519867c738c4a8d52e912a611d',
    '7c6515850eae88194d3da2ed7ba837e36173d69f0b502af9f52a2a6cbe95da7a',
    'b91b3f422260ad900cc425721cd52f864960a458b0321cc96092636042f467d5',
    '2fd71dbaf1cdf50e9f9f18502da1d861211eb861b943db319d562e7086dbce21',
), strict=True))


def contract():
    base, archived = discovery.discovery_contract()
    frozen = json.loads(transfer.read_locked(checkpoint.FIT, checkpoint.FIT_SHA))
    if digest(base) != frozen['planSha256'] or digest(frozen['plan']) != frozen['planSha256']:
        raise ValueError('The earlier quoted fit must reproduce its discovery seal')
    miss, passed = frozen['fitted'][adaptive.ADAPTIVE]['actions']
    depth = (miss,) + (passed,) * (base['caseCounts'][2] - 1)
    root = transfer.ROOT
    sources = (Path(__file__).resolve(), root / 'cpo/qualification_prefix_cycle.py',
               root / 'cpo/two_sided_certificate_cycle.py')
    plan = {**base, 'protocol': 'qualification-prefix-depth-fit-v1', 'originalFitSha256': checkpoint.FIT_SHA,
            'originalDepthActions': depth, 'maximumUpdates': 2,
            'sourceSha256': {**base['sourceSha256'], **{str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
                                                       for path in sources}},
            'scope': 'Begin with the frozen quoted first-reply fit. Consider every allowed change of one '
                     'first-miss position, with all quoted screens eligible. Make at most two improving updates. '
                     'Each choice maximizes discovery passes and then minimizes lookups under the original '
                     'router budget for every discovery cohort. Use the original already-paid qualification '
                     'prefix, and exclude every target task. Carry the selected table into all target cycles.'}
    return plan, base, archived, frozen


def neighborhood(table, actions):
    return sorted({table, *(table[:index] + (action,) + table[index + 1:]
                            for index in range(len(table)) for action in actions)})


def first_miss(grades, rows):
    return next((index for index, row in enumerate(rows) if not grades[row]), len(rows))


def sweep(plan, groups, schemas, engines):
    available = {table: {} for table in schemas}
    run = native.paired.cycle.execute_path
    cap = max(limit for _, _, _, limit in plan['controls'])
    for cohort, panels in groups.items():
        enrollment = set(map(tuple, plan['fitEnrollment'][cohort]))
        if not enrollment:
            continue
        totals = {table: Counter() for table in schemas}
        for subject, model, matrix in panels:
            if (subject, model) not in enrollment:
                continue
            cells, _ = transfer.case_cells(matrix)
            for seed in plan['seeds']:
                start, stages = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
                held = stages[0][2][-1]
                grades = {prompt: sum(cells[prompt][row] for row in held)
                          for prompt in {start, *(prompt for _, roster, _ in stages for prompt in roster)}}

                @cache
                def state(index, current):
                    return first_miss(cells[current], stages[index][2][2])

                @cache
                def step(index, current, action):
                    local_seed, roster, roles = stages[index]
                    result, ledger = run(engines[action], cells, current, roster, roles, local_seed, cap, 1)
                    prefix = roles[2][:state(index, current) + 1]
                    expected = [('qualification', current, str(case)) for case in prefix]
                    if list(ledger)[:len(expected)] != expected:
                        raise ValueError('The selected state must be exposed by the paid incumbent prefix')
                    continuous.routing.verify_qualification(cells, current, roles, result, ledger, 1)
                    return result.prompt, len(ledger)

                for table in schemas:
                    current, cost = start, 0
                    for index in range(len(stages)):
                        depth = state(index, current)
                        action = table[depth] if depth < len(table) else adaptive.RETAIN
                        current, spent = step(index, current, action)
                        cost += spent
                    totals[table].update(holdoutPasses=grades[current], paidLookups=cost)
                state.cache_clear()
                step.cache_clear()
        for table, point in totals.items():
            available[table][cohort] = point
    return available


def rank(points):
    return (-sum(value['holdoutPasses'] for value in points.values()), sum(value['paidLookups'] for value in points.values()))


def fit(plan, groups, frozen):
    options = discovery.screens_with_quotes(plan)
    engines = {name: partial(_run, screen=screen) for name, screen in options.items()}
    current = tuple(plan['originalDepthActions'])
    budgets = {name: point['paidLookups'] for name, point in frozen['baseline'].items()}
    rounds, original = [], None
    for _ in range(plan['maximumUpdates']):
        choices = neighborhood(current, plan['actions'])
        totals = sweep(plan, groups, choices, engines)
        if original is None:
            original = totals[current]
            if original != frozen['fitted'][adaptive.ADAPTIVE]['byCohort']:
                raise ValueError('The original quoted discovery fit must reproduce to every cohort total')
        chosen = adaptive.promotion.choose_actions(totals, budgets, False)
        round_measured = {'tested': len(choices), 'before': current, 'after': chosen,
                          'attained': totals[chosen], 'menuSha256': digest({'|'.join(k): v for k, v in totals.items()})}
        rounds.append(round_measured)
        if rank(totals[chosen]) >= rank(totals[current]):
            round_measured['after'] = current
            round_measured['attained'] = totals[current]
            break
        current = chosen
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'rounds': rounds,
            'original': original, 'actions': current, 'budgets': budgets}


def target_plan(cohort, plan, base, archived, frozen, fitted):
    if fitted['planSha256'] != digest(plan) or digest(fitted['plan']) != fitted['planSha256']:
        raise ValueError('The position policy must come from the sealed discovery fit')
    inherited, panels, models, static, gepa, simple, _, _ = discovery.prepare_target(cohort, base, frozen, archived)
    lock = RECEIPTS[cohort]
    path = f'docs/quoted-schedule-discovery-transfer-{cohort.lower()}-v1.json'
    previous = json.loads(transfer.read_locked(path, lock))
    if previous['planSha256'] != digest(inherited):
        raise ValueError('The target replay must preserve the exact earlier quoted transfer')
    target = {**inherited, 'protocol': 'qualification-prefix-depth-transfer-v1', 'originalTransferSha256': lock,
              'depthFitSha256': digest(fitted), 'sourceSha256': {**inherited['sourceSha256'], **plan['sourceSha256']},
              'actions': fitted['actions'], 'originalDepthActions': plan['originalDepthActions'],
              'scope': 'Replay the fitted position table, the earlier quoted first-reply table through the '
                       'same dispatcher, and the original router. Verify the earlier paid traces and reprice '
                       'simple controls and native GEPA at the position table’s actual lookup count.'}
    return target, panels, models, static, gepa, simple, previous['results']


def replay(plan, panels, models, static, gepa, simple, previous):
    screens = discovery.screens_with_quotes(plan)
    runners = {name: partial(run_qualification_prefix_cycle, screens=tuple(screens[action] for action in table))
               for name, table in ((ORIGINAL, plan['originalDepthActions']), (DEPTH, plan['actions']))}
    runners[ROUTED] = adaptive.routed_runner(plan, models, static)
    vectors = {}
    schedules = {name: dict.fromkeys(plan['subjects'], name) for name in runners}
    totals, hashes = adaptive.replay(plan, panels, runners, schedules, vectors)
    for name in (ORIGINAL, ROUTED):
        if totals[name] != previous['policies'][name] or any(
                path[name] != previous['trajectoryHashes'][panel][name] for panel, path in hashes.items()):
            raise ValueError('The new dispatcher must preserve both the original transfer and router paid paths')
    spend = totals[DEPTH]['paidLookups']
    controls = parent.compare_simple(plan, panels, simple, spend, vectors)
    bounds, attainers = parent.compare_native(plan, panels, gepa, spend,
                                               simple['settingsTotals'][adaptive.RETAIN]['holdoutPasses'], vectors)
    paired = native.frozen.paired_effects.paired_effect
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'simpleAtBudget': controls,
            'nativeBoundsAtBudget': bounds, 'replayedNativeAnchors': attainers, 'trajectoryHashes': hashes,
            'pairedDepth': {name: paired(vectors, DEPTH, name, plan) for name in (ORIGINAL, ROUTED, *controls, *attainers)}}


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
            parser.error('Target replay requires a frozen fitted receipt')
        plan, *inputs = target_plan(args.cohort, plan, base, archived, frozen, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, _, _ = discovery.training(base)
        report = fit(plan, groups, frozen)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
