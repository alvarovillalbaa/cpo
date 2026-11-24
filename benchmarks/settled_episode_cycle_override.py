"""Fit one cycle's schedule override using only paid opening grades."""

import argparse
from collections import Counter
from functools import cache
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_refit as refit
from benchmarks.paid_prefix_archive_routing import verify_qualification
from cpo._contract import digest


BUDGET_ONLY, GUARDED = 'budget-only', 'cohort-floors'


def constant_paths(table):
    return tuple((action,) * 3 for action in table)


def override_menus(anchors, options):
    for name, anchor in anchors.items():
        for cycle in range(3):
            yield name, cycle, tuple(
                tuple((*path[:cycle], action, *path[cycle + 1:]) for action in options)
                for path in anchor
            )


def fit_tables(menus, anchors, baseline, counts, scores, support, min_subjects):
    """Optimize after paying for the shortest prefix that settles the entire path."""
    best, ranks, feasible = {}, {}, Counter()
    seen = set()
    for anchor, cycle, menu in menus:
        choices = tuple(
            paths if support[state] >= min_subjects else (anchors[anchor][state],)
            for state, paths in enumerate(menu)
        )
        for actions in product(*choices):
            if actions in seen:
                continue
            seen.add(actions)
            points = {}
            for cohort, floor in baseline.items():
                columns = [scores[cohort, state, path] for state, path in enumerate(actions)]
                lookup_cost = sum(column['paidLookups'] for column in columns)
                lookup_cost += refit.probe_cost(actions, counts[cohort][False], counts[cohort][True], settled=True)
                if lookup_cost > floor['paidLookups']:
                    break
                points[cohort] = {'paidLookups': lookup_cost,
                                  'holdoutPasses': sum(column['holdoutPasses'] for column in columns)}
            else:
                priority = (-sum(point['holdoutPasses'] for point in points.values()),
                            sum(point['paidLookups'] for point in points.values()), actions)
                changed_cycle = cycle + 1 if actions != anchors[anchor] else None
                record = {'paths': actions, 'anchor': anchor, 'overrideCycle': changed_cycle, 'points': points}
                for mode in (BUDGET_ONLY, GUARDED):
                    if mode == GUARDED and any(
                        points[cohort]['holdoutPasses'] < floor['holdoutPasses']
                        for cohort, floor in baseline.items()
                    ):
                        continue
                    feasible[mode] += 1
                    if mode not in ranks or priority < ranks[mode]:
                        ranks[mode], best[mode] = priority, record
    if len(best) != 2:
        raise ValueError('The bounded opening must remain an affordable discovery anchor')
    return {'policies': best, 'feasibleTables': feasible, 'support': support, 'uniqueTables': len(seen)}


def rollout_graph(plan, cells, stages, runners):
    cap = max(limit for _, _, _, limit in plan['controls'])
    execute = refit.native.paired.cycle.execute_path
    held = stages[0][2][-1]

    @cache
    def step(index, incumbent, action):
        if action == refit.RETAIN:
            return incumbent, 0
        seed, roster, roles = stages[index]
        result, ledger = execute(runners[action], cells, incumbent, roster, roles, seed, cap, 1)
        verify_qualification(cells, incumbent, roles, result, ledger, 1)
        return result.prompt, len(ledger)

    def rollout(incumbent, path):
        paid = 0
        for index, action in enumerate(path):
            incumbent, reads = step(index, incumbent, action)
            paid += reads
        return [cells[incumbent][case] for case in held], paid

    return rollout, step.cache_clear


def runners(plan, models, static):
    original, reordered = refit.engines(plan, models, static)
    return {**original, **reordered}


def discovery(plan, groups, models, static, anchors, frozen):
    engines = runners(plan, models, static)
    menus = tuple(override_menus(anchors, tuple(sorted(engines))))
    paths = tuple(sorted({path for _, _, menu in menus for path in menu[state]}) for state in range(3))
    baseline = frozen['baseline']
    counts = {cohort: Counter() for cohort in baseline}
    support = [set() for _ in range(3)]
    scores = {(cohort, state, path): Counter()
              for cohort in baseline for state in range(3) for path in paths[state]}
    cohort_references = (refit.BOUNDED, refit.SETTLED)
    references = {cohort: {name: Counter() for name in cohort_references} for cohort in baseline}
    for cohort in baseline:
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in enrolled]
        excluded = set(plan['targetSubjectsExcluded'])
        if {panel[:2] for panel in panels} != enrolled or {name for name, _ in enrolled} & excluded:
            raise ValueError('Use the sealed discovery enrollment, disjoint from target tasks')
        for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
            state, ledger = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
            state = int(state)
            counts[cohort][ledger[0][2]] += 1
            support[state].add(subject)
            rollout, clear = rollout_graph(plan, cells, stages, engines)
            for path in paths[state]:
                grades, paid = rollout(start, path)
                scores[cohort, state, path].update(holdoutPasses=sum(grades), paidLookups=paid)
            clear()
        for reference in cohort_references:
            table = anchors[reference]
            for state in range(3):
                references[cohort][reference].update(scores[cohort, state, table[state]])
            references[cohort][reference].update(paidLookups=refit.probe_cost(
                table, counts[cohort][False], counts[cohort][True], settled=True,
            ))
        if (references[cohort][refit.BOUNDED] != baseline[cohort]
                or references[cohort][refit.SETTLED] != frozen['fitted'][refit.SETTLED]['points'][cohort]):
            raise ValueError('Discovery must reproduce both anchor scores and costs')
    return fit_tables(menus, anchors, baseline, counts, scores, list(map(len, support)), plan['minSubjectsPerState'])


def target_replay(plan, panels, models, static, gepa, simple, tables, archived):
    engines = runners(plan, models, static)
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    totals, choices, vectors = {name: Counter() for name in tables}, {name: Counter() for name in tables}, {}
    for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
        rollout, clear = rollout_graph(plan, cells, stages, engines)
        state, paid = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
        for name, table in tables.items():
            path, training = refit.route(cells, stages, start, table)
            expected = refit.probe_cost(table, int(not paid[0][2]), int(paid[0][2]), settled=True)
            if path != table[int(state)] or training != paid[:expected]:
                raise ValueError('The executed training route must match the fitted path and paid prefix')
            grades, cost = rollout(start, path)
            totals[name].update(holdoutPasses=sum(grades), paidLookups=cost + len(training),
                                trainingLookups=len(training))
            choices[name][str(int(state))] += 1
            add(vectors.setdefault(subject, {}).setdefault(name, [0] * len(grades)), grades)
        clear()
    if any(totals[name] != archived['policies'][name] for name in (refit.BOUNDED, refit.SETTLED)):
        raise ValueError('Both anchor policies must match the locked target totals')

    @cache
    def matched(budget):
        peers = {subject: dict(scores) for subject, scores in vectors.items()}
        controls = refit.parent.compare_simple(plan, panels, simple, budget, peers)
        bounds, anchors = refit.parent.compare_native(
            plan, panels, gepa, budget, simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], peers,
        )
        return controls, bounds, anchors, peers

    comparisons = {}
    paired = refit.native.frozen.paired_effects.paired_effect
    for name in (BUDGET_ONLY, GUARDED):
        controls, bounds, anchors, peers = matched(totals[name]['paidLookups'])
        comparisons[name] = {'nativeBoundsAtCost': bounds, 'nativeAnchors': anchors, 'simpleAtCost': controls,
                             'paired': {peer: paired(peers, name, peer, plan)
                                        for peer in (refit.BOUNDED, refit.SETTLED, *controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']),
            'policies': totals, 'routes': choices, 'comparisons': comparisons}


def verify():
    transfer = refit.transfer
    plan, context, baseline = refit.contract()
    if version('gepa') != plan['gepaVersion'] or plan['cycles'] != 3:
        raise ValueError('Use the pinned GEPA version and the three-cycle study')
    frozen = json.loads(transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    anchors = {refit.BOUNDED: constant_paths((refit.BOUNDED,) * 3),
               refit.SETTLED: constant_paths(frozen['fitted'][refit.SETTLED]['actions'])}
    groups, models, static = refit.discovery.training(context[2])
    fit = discovery(plan, groups, models, static, anchors, frozen)
    tables = {**anchors, **{name: item['paths'] for name, item in fit['policies'].items()}}

    targets = {}
    for cohort in refit.discovery.COHORTS:
        target, (panels, models, static, gepa, simple, _) = refit.target(cohort, plan, context, baseline, frozen)
        name = cohort.lower()
        archived = json.loads(transfer.read_locked(
            f'docs/settled-episode-refit-transfer-{name}-v1.json', parity.LOCKS[name],
        ))
        if digest(target) != archived['planSha256'] or digest(archived['plan']) != archived['planSha256']:
            raise ValueError('Use the original layout and comparison witnesses')
        targets[cohort] = target_replay(target, panels, models, static, gepa, simple, tables, archived['results'])
    return {'protocol': 'settled-episode-cycle-override-v1',
            'fitReceiptSha256': parity.FIT_SHA, 'transferReceiptSha256': parity.LOCKS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'anchorTables': anchors, 'discovery': fit, 'archivedTransfer': targets, 'providerRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a fresh receipt path')
    result = verify()
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
