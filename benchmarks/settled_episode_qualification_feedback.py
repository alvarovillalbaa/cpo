"""Fit follow-up schedules on observed qualification outcomes at matched discovery cost."""

import argparse
from collections import Counter, defaultdict
from functools import cache
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_cycle_override as override
from benchmarks import settled_episode_refit as refit
from benchmarks.paid_prefix_archive_routing import verify_qualification
from cpo._contract import digest


ALWAYS, CONDITIONAL = 'unconditional-follow-up', 'qualification-feedback'
OUTCOMES = ('precheck-closed', 'no-finalist', 'finalist-rejected', 'promoted')
ANY = 'any-previous-cycle'


def rule(base, outcome='', replacement=None):
    return (base, '', base) if replacement is None or replacement == base else (base, outcome, replacement)


def outcome(result):
    if result.promoted:
        return 'promoted'
    if result.search.finalist is not None:
        return 'finalist-rejected'
    observations = result.qualification.observations if result.qualification is not None else ()
    if observations and all(reply.passed for reply in observations):
        return 'precheck-closed'
    return 'no-finalist'


def rollout_graph(plan, cells, stages, engines):
    cap = max(limit for _, _, _, limit in plan['controls'])
    execute = refit.native.paired.cycle.execute_path
    held = stages[0][2][-1]

    @cache
    def step(index, incumbent, action):
        if action == refit.RETAIN:
            return incumbent, 0, 'skipped'
        seed, roster, roles = stages[index]
        result, paid = execute(engines[action], cells, incumbent, roster, roles, seed, cap, 1)
        verify_qualification(cells, incumbent, roles, result, paid, 1)
        return result.prompt, len(paid), outcome(result)

    @cache
    def rollout(start, policy):
        base, trigger, replacement = policy
        incumbent, history, paid, switched = start, [], 0, 0
        for index in range(len(stages)):
            change = bool(history and (trigger == ANY or trigger == history[-1]))
            incumbent, cost, observed = step(index, incumbent, replacement if change else base)
            history.append(observed)
            paid += cost
            switched += change
        return [cells[incumbent][case] for case in held], paid, tuple(history), switched

    def clear():
        rollout.cache_clear()
        step.cache_clear()

    return rollout, clear


def fit_tables(anchors, options, baseline, counts, points, support, minimum):
    """Choose a single common trigger and one follow-up action per opening state."""
    best, ranks, feasible, examined = {}, {}, Counter(), Counter()
    for name, actions in anchors.items():
        for trigger in (ANY, *OUTCOMES):
            family = ALWAYS if trigger == ANY else CONDITIONAL
            menus = tuple(tuple(rule(base, trigger, action) for action in options)
                          if len(support[name, state, trigger]) >= minimum else (rule(base),)
                          for state, base in enumerate(actions))
            for table in product(*menus):
                if all(not entry[1] for entry in table) and trigger not in (ANY, OUTCOMES[0]):
                    continue
                examined[family] += 1
                per_cohort = {}
                for cohort, cap in baseline.items():
                    columns = [points[cohort, state, entry] for state, entry in enumerate(table)]
                    cost = sum(column['paidLookups'] for column in columns)
                    cost += refit.probe_cost(table, counts[cohort][False], counts[cohort][True], settled=True)
                    if cost > cap:
                        break
                    per_cohort[cohort] = {'holdoutPasses': sum(column['holdoutPasses'] for column in columns),
                                          'paidLookups': cost}
                else:
                    feasible[family] += 1
                    rank = (-sum(item['holdoutPasses'] for item in per_cohort.values()),
                            sum(item['paidLookups'] for item in per_cohort.values()), table)
                    if family not in ranks or rank < ranks[family]:
                        ranks[family] = rank
                        best[family] = {
                            'anchor': name, 'trigger': trigger if any(entry[1] for entry in table) else None,
                            'rules': table, 'points': per_cohort,
                            'discoverySupport': [len(support[name, state, trigger]) for state in range(3)],
                        }
    if len(best) != 2:
        raise ValueError('The frozen control must remain feasible in both policy families')
    return {'policies': best, 'examinedTables': examined, 'feasibleTables': feasible, 'budgets': baseline}


def discovery(plan, groups, models, static, anchors, frozen):
    engines = override.runners(plan, models, static)
    options = tuple(sorted(engines))
    baseline = frozen['baseline']
    fixed = frozen['fitted'][refit.SETTLED]['points']
    counts = {cohort: Counter() for cohort in baseline}
    points, support = defaultdict(Counter), defaultdict(set)
    for cohort in baseline:
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in enrolled]
        if {panel[:2] for panel in panels} != enrolled or (
            {subject for subject, _ in enrolled} & set(plan['targetSubjectsExcluded'])
        ):
            raise ValueError('Use the sealed discovery enrollment, disjoint from target tasks')
        for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
            state, paid = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
            state = int(state)
            counts[cohort][paid[0][2]] += 1
            rollout, clear = rollout_graph(plan, cells, stages, engines)
            measured = set()
            for name, actions in anchors.items():
                base = actions[state]
                _, _, history, _ = rollout(start, rule(base))
                reachable = (ANY, *sorted(set(history[:-1])))
                for signal in reachable:
                    support[name, state, signal].add(subject)
                for signal, alternative in product((ANY, *OUTCOMES), options):
                    candidate = rule(base, signal, alternative)
                    if candidate in measured:
                        continue
                    measured.add(candidate)
                    grades, lookups, _, _ = rollout(start, candidate)
                    points[cohort, state, candidate].update(holdoutPasses=sum(grades), paidLookups=lookups)
            clear()
        for name, reference in ((refit.BOUNDED, baseline), (refit.SETTLED, fixed)):
            table = tuple(rule(action) for action in anchors[name])
            result = Counter()
            for state, candidate in enumerate(table):
                result.update(points[cohort, state, candidate])
            result.update(paidLookups=refit.probe_cost(
                table, counts[cohort][False], counts[cohort][True], settled=True,
            ))
            if result != reference[cohort]:
                raise ValueError('Discovery must reproduce both frozen references')
    budgets = {cohort: point['paidLookups'] for cohort, point in fixed.items()}
    return fit_tables(anchors, options, budgets, counts, points, support, plan['minSubjectsPerState'])


def transfer_point(plan, panels, models, static, gepa, simple, tables, archived):
    engines = override.runners(plan, models, static)
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    totals, vectors = {name: Counter() for name in tables}, {}
    for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
        rollout, clear = rollout_graph(plan, cells, stages, engines)
        state, paid = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
        for name, table in tables.items():
            action, training = refit.route(cells, stages, start, table)
            expected = refit.probe_cost(table, int(not paid[0][2]), int(paid[0][2]), settled=True)
            if action != table[int(state)] or training != paid[:expected]:
                raise ValueError('Training costs and the sealed opening prefix must agree')
            grades, cost, _, switches = rollout(start, action)
            totals[name].update(holdoutPasses=sum(grades), paidLookups=cost + len(training),
                                trainingLookups=len(training), overriddenCycles=switches)
            add(vectors.setdefault(subject, {}).setdefault(name, [0] * len(grades)), grades)
        clear()
    for name in (refit.BOUNDED, refit.SETTLED):
        point = totals[name]
        if point['overriddenCycles'] or {key: point[key] for key in archived['policies'][name]} != archived['policies'][name]:
            raise ValueError('The anchor policies must match their original archived costs and scores')

    @cache
    def matched(budget):
        peers = {subject: dict(scores) for subject, scores in vectors.items()}
        controls = refit.parent.compare_simple(plan, panels, simple, budget, peers)
        bounds, anchors = refit.parent.compare_native(
            plan, panels, gepa, budget, simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], peers,
        )
        return controls, bounds, anchors, peers

    effects = refit.native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name in (ALWAYS, CONDITIONAL):
        controls, bounds, anchors, peers = matched(totals[name]['paidLookups'])
        comparisons[name] = {'nativeBoundsAtCost': bounds, 'nativeAnchors': anchors, 'simpleAtCost': controls,
                             'paired': {peer: effects(peers, name, peer, plan) for peer in
                                        (refit.BOUNDED, refit.SETTLED, *controls, *anchors)}}
    comparisons[CONDITIONAL]['paired'][ALWAYS] = effects(vectors, CONDITIONAL, ALWAYS, plan)
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'comparisons': comparisons}


def verify():
    transfer = refit.transfer
    plan, context, baseline = refit.contract()
    if version('gepa') != plan['gepaVersion'] or plan['cycles'] != 3:
        raise ValueError('Use the pinned GEPA version and three-cycle archive')
    frozen = json.loads(transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    anchors = {refit.BOUNDED: (refit.BOUNDED,) * 3, refit.SETTLED: tuple(frozen['fitted'][refit.SETTLED]['actions'])}
    groups, models, static = refit.discovery.training(context[2])
    fit = discovery(plan, groups, models, static, anchors, frozen)
    tables = {name: tuple(rule(base) for base in actions) for name, actions in anchors.items()}
    tables.update({name: item['rules'] for name, item in fit['policies'].items()})

    targets = {}
    for cohort in refit.discovery.COHORTS:
        target, (panels, models, static, gepa, simple, _) = refit.target(cohort, plan, context, baseline, frozen)
        name = cohort.lower()
        archived = json.loads(transfer.read_locked(
            f'docs/settled-episode-refit-transfer-{name}-v1.json', parity.LOCKS[name],
        ))
        if digest(target) != archived['planSha256'] or digest(archived['plan']) != archived['planSha256']:
            raise ValueError('Use the locked target geometry and GEPA witnesses')
        targets[cohort] = transfer_point(target, panels, models, static, gepa, simple, tables, archived['results'])
    sources = (Path(__file__).resolve(), Path(override.__file__).resolve())
    return {'protocol': 'settled-episode-qualification-feedback-v1',
            'sourceSha256': {str(file.relative_to(transfer.ROOT)): sha256(file.read_bytes()).hexdigest()
                             for file in sources},
            'fitReceiptSha256': parity.FIT_SHA, 'transferReceiptSha256': parity.LOCKS,
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
