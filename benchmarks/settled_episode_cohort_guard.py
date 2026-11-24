"""Fit a settled schedule with separate quality and cost floors per discovery cohort."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_refit as refit
from cpo._contract import digest


GUARDED = 'discovery-cohort-guard'


def guarded_table(rows, options, baseline, min_subjects):
    """Maximize passes among tables that match every cohort's baseline quality and budget."""
    cohorts = tuple(baseline)
    states = [set() for _ in range(3)]
    counts = {cohort: Counter() for cohort in cohorts}
    totals = {(state, option, cohort): Counter()
              for state, option, cohort in product(range(3), options, cohorts)}
    for cohort, subject, pair, menu in rows:
        state = sum(pair)
        states[state].add(subject)
        counts[cohort][pair[0]] += 1
        for option, point in menu.items():
            totals[state, option, cohort].update(holdoutPasses=point.passes, paidLookups=point.cost)

    menus = [options if len(subjects) >= min_subjects else (refit.RETAIN,) for subjects in states]
    best, rank, feasible = None, None, 0
    for actions in product(*menus):
        points = {}
        for cohort, floor in baseline.items():
            columns = [totals[state, choice, cohort] for state, choice in enumerate(actions)]
            passes = sum(point['holdoutPasses'] for point in columns)
            if passes < floor['holdoutPasses']:
                break
            cost = sum(point['paidLookups'] for point in columns)
            cost += refit.probe_cost(actions, counts[cohort][False], counts[cohort][True], settled=True)
            if cost > floor['paidLookups']:
                break
            points[cohort] = {'holdoutPasses': passes, 'paidLookups': cost}
        else:
            feasible += 1
            priority = (-sum(point['holdoutPasses'] for point in points.values()),
                        sum(point['paidLookups'] for point in points.values()), actions)
            if rank is None or priority < rank:
                rank = priority
                best = {'actions': actions, 'points': points}
    if best is None:
        raise ValueError('The discovery cohort floors require an affordable anchor')
    return {**best, 'feasibleTables': feasible, 'support': list(map(len, states))}


def discovery_rows(plan, groups, models, static, baseline):
    engines = refit.engines(plan, models, static)
    menu = tuple(sorted(engines[0]))
    rows, observed = [], {}
    for cohort in baseline:
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in enrolled]
        covered = {panel[:2] for panel in panels}
        if covered != enrolled or {subject for subject, _ in covered} & set(plan['targetSubjectsExcluded']):
            raise ValueError('Use the sealed discovery enrollment, disjoint from target tasks')
        tally = Counter()
        for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
            rollout = refit.episode(plan, cells, stages, start, *engines)
            options = {}
            for action in menu:
                grades, old_price, price = rollout(action)
                options[action] = refit.frontier.Point(sum(grades), price, (action,))
                if action == refit.BOUNDED:
                    tally.update(holdoutPasses=sum(grades), paidLookups=old_price)
            rollout.cache_clear()
            _, paid = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
            rows.append((cohort, subject, tuple(reply for _, _, reply in paid), options))
        observed[cohort] = tally
    if observed != baseline:
        raise ValueError('Each bounded-opening discovery score and price must reproduce')
    return menu, rows


def transfer_point(plan, panels, models, static, gepa, simple, table, archived):
    engines = refit.engines(plan, models, static)
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    tallies = {policy: Counter() for policy in (refit.SETTLED, refit.BOUNDED, GUARDED)}
    vectors, choices = {}, Counter()
    original = plan['revisedActions'][refit.SETTLED]
    for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
        rollout = refit.episode(plan, cells, stages, start, *engines)
        for policy, actions in ((refit.BOUNDED, (refit.BOUNDED,) * 3),
                                (refit.SETTLED, original), (GUARDED, table)):
            action, probe_ledger = refit.route(cells, stages, start, actions)
            grades, _, spent = rollout(action)
            cost = len(probe_ledger)
            target = vectors.setdefault(subject, {}).setdefault(policy, [0] * len(grades))
            add(target, grades)
            tallies[policy].update(holdoutPasses=sum(grades), paidLookups=spent + cost, trainingLookups=cost)
            if policy == GUARDED:
                choices[action] += 1
        rollout.cache_clear()
    if any(tallies[policy] != archived['policies'][policy] for policy in (refit.BOUNDED, refit.SETTLED)):
        raise ValueError('Reproduce the original reference points before evaluating the guarded fit')
    budget = tallies[GUARDED]['paidLookups']
    matched = refit.parent.compare_simple(plan, panels, simple, budget, vectors)
    bounds, anchors = refit.parent.compare_native(
        plan, panels, gepa, budget, simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], vectors,
    )
    effect = refit.native.frozen.paired_effects.paired_effect
    return {'episodes': sum(choices.values()), 'policies': tallies, 'guardedDecisions': choices,
            'simpleAtBudget': matched, 'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors,
            'paired': {peer: effect(vectors, GUARDED, peer, plan)
                       for peer in (refit.BOUNDED, refit.SETTLED, *matched, *anchors)},
            'referenceBoundsAtOwnBudget': archived['comparisons'][refit.SETTLED]['nativeBoundsAtBudget']}


def verify():
    transfer = refit.transfer
    plan, context, baseline = refit.contract()
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    frozen = json.loads(transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    groups, models, static = refit.discovery.training(context[2])
    menu, rows = discovery_rows(plan, groups, models, static, frozen['baseline'])
    policy = guarded_table(rows, menu, frozen['baseline'], plan['minSubjectsPerState'])
    unguarded = refit.fit_table(rows, menu, frozen['budget'], plan['minSubjectsPerState'], settled=True)
    if digest(unguarded) != digest(frozen['fitted'][refit.SETTLED]):
        raise ValueError('The discovery data must reproduce the original fit')
    table = policy['actions']

    results = {}
    for cohort in refit.discovery.COHORTS:
        target, (panels, models, static, gepa, simple, _) = refit.target(cohort, plan, context, baseline, frozen)
        name = cohort.lower()
        previous = json.loads(transfer.read_locked(
            f'docs/settled-episode-refit-transfer-{name}-v1.json', parity.LOCKS[name],
        ))
        if digest(target) != previous['planSha256'] or digest(previous['plan']) != previous['planSha256']:
            raise ValueError('The target layout must match the original sealed transfer')
        results[cohort] = transfer_point(target, panels, models, static, gepa, simple, table, previous['results'])
    return {
        'protocol': 'settled-episode-discovery-cohort-guard-v1',
        'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'fitReceiptSha256': parity.FIT_SHA,
        'transferReceiptSha256': parity.LOCKS,
        'discovery': {'baseline': frozen['baseline'], 'unguarded': unguarded, 'guarded': policy},
        'archivedTransfer': results,
        'providerRequests': 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a fresh receipt path')
    report = verify()
    with args.out.open('x') as output:
        output.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
