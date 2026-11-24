"""Distinguish rejected finalists with and without a paid, paired loss."""

import argparse
from collections import Counter, defaultdict
from functools import cache
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_feedback_api_parity as prior_api
from benchmarks import settled_episode_qualification_feedback as feedback
from benchmarks import settled_episode_refit as refit
from benchmarks.paid_prefix_archive_routing import verify_qualification
from cpo._contract import digest


CANDIDATE = 'paired-loss-feedback'
SUBTYPES = ('no-paired-loss-observed', 'paired-loss-observed')


def paired_loss(incumbent, finalist, observations):
    incumbent_passes = {(item.row_id, item.repeat) for item in observations
                        if item.prompt == incumbent and item.passed is True}
    return any(item.prompt == finalist and item.passed is False
               and (item.row_id, item.repeat) in incumbent_passes for item in observations)


def rollout_graph(plan, cells, stages, engines):
    cap = max(limit for _, _, _, limit in plan['controls'])
    execute = refit.native.paired.cycle.execute_path
    held = stages[0][2][-1]

    @cache
    def step(index, incumbent, action):
        if action == refit.RETAIN:
            return incumbent, 0, None
        seed, roster, roles = stages[index]
        result, ledger = execute(engines[action], cells, incumbent, roster, roles, seed, cap, 1)
        verify_qualification(cells, incumbent, roles, result, ledger, 1)
        signal = None
        decision = result.qualification
        if result.search.finalist is not None and decision is not None and decision.status == 'rejected':
            signal = int(paired_loss(incumbent, result.search.finalist, decision.observations))
        return result.prompt, len(ledger), signal

    def rollout(start, rule):
        incumbent, history, paid, switched, signal = start, [], 0, 0, None
        for index in range(len(stages)):
            action = rule[0] if signal is None else rule[1 + signal]
            incumbent, cost, signal = step(index, incumbent, action)
            history.append(signal)
            paid += cost
            switched += action != rule[0]
        return [cells[incumbent][case] for case in held], paid, tuple(history), switched

    return rollout, step.cache_clear


def menu(rule, subtype, options):
    return tuple((*rule[:subtype + 1], action, *rule[subtype + 2:]) for action in options)


def fit_tables(reference, options, budgets, counts, points, support, minimum):
    """Vary one rejection subtype and retain the frozen action for its peer."""
    best, rank, feasible, explored = None, None, 0, set()
    for subtype in range(len(SUBTYPES)):
        allowed = [menu(rule, subtype, options) if len(support[state, subtype]) >= minimum else (rule,)
                   for state, rule in enumerate(reference)]
        for table in product(*allowed):
            if table in explored:
                continue
            explored.add(table)
            per_cohort = {}
            for cohort, cap in budgets.items():
                groups = [points[cohort, state, rule] for state, rule in enumerate(table)]
                cost = sum(group['paidLookups'] for group in groups)
                cost += refit.probe_cost(table, counts[cohort][False], counts[cohort][True], settled=True)
                if cost > cap:
                    break
                per_cohort[cohort] = {'holdoutPasses': sum(group['holdoutPasses'] for group in groups),
                                      'paidLookups': cost}
            else:
                feasible += 1
                priority = (-sum(point['holdoutPasses'] for point in per_cohort.values()),
                            sum(point['paidLookups'] for point in per_cohort.values()), table)
                if rank is None or priority < rank:
                    rank = priority
                    best = {'rules': table, 'alteredSubtype': SUBTYPES[subtype] if table != reference else None,
                            'points': per_cohort}
    if best is None:
        raise ValueError('The frozen feedback policy must remain feasible')
    return {**best, 'feasibleTables': feasible, 'distinctTables': len(explored),
            'support': {name: [len(support[state, index]) for state in range(3)]
                        for index, name in enumerate(SUBTYPES)}}


def discovery(plan, groups, models, static, rules, archived):
    engines = feedback.override.runners(plan, models, static)
    options = tuple(sorted(engines))
    available = [tuple(sorted({*menu(rule, 0, options), *menu(rule, 1, options)})) for rule in rules]
    counts, points, support = {cohort: Counter() for cohort in archived}, defaultdict(Counter), defaultdict(set)
    excluded = set(plan['targetSubjectsExcluded'])
    for cohort in archived:
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in enrolled]
        if {panel[:2] for panel in panels} != enrolled or {subject for subject, _ in enrolled} & excluded:
            raise ValueError('Reproduce the original task-disjoint discovery enrollment')
        for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
            state, probe = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
            state = int(state)
            counts[cohort][probe[0][2]] += 1
            rollout, clear = rollout_graph(plan, cells, stages, engines)
            for rule in available[state]:
                grades, cost, history, _ = rollout(start, rule)
                points[cohort, state, rule].update(holdoutPasses=sum(grades), paidLookups=cost)
                if rule == rules[state]:
                    for subtype in set(history[:-1]) - {None}:
                        support[state, subtype].add(subject)
            clear()
        totals = Counter()
        for state, rule in enumerate(rules):
            totals.update(points[cohort, state, rule])
        totals.update(paidLookups=refit.probe_cost(rules, counts[cohort][False], counts[cohort][True], settled=True))
        if totals != archived[cohort]:
            raise ValueError('Distinguishing losses must reproduce the frozen reference when both actions agree')
    budgets = {cohort: point['paidLookups'] for cohort, point in archived.items()}
    return fit_tables(rules, options, budgets, counts, points, support, plan['minSubjectsPerState'])


def target_replay(plan, panels, models, static, gepa, simple, tables, archived):
    engines = feedback.override.runners(plan, models, static)
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    totals, vectors, signals = {label: Counter() for label in tables}, {}, Counter()
    for subject, _, _, cells, stages, start in refit.previous.episodes(plan, panels):
        state, probe = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
        rollout, clear = rollout_graph(plan, cells, stages, engines)
        for label, table in tables.items():
            rule, paid = refit.route(cells, stages, start, table)
            expected = refit.probe_cost(table, int(not probe[0][2]), int(probe[0][2]), settled=True)
            if table[int(state)] != rule or paid != probe[:expected]:
                raise ValueError('Actual opening probes must agree with the frozen route and cost')
            grades, cost, history, switches = rollout(start, rule)
            totals[label].update(holdoutPasses=sum(grades), paidLookups=cost + len(paid),
                                 trainingLookups=len(paid), overriddenCycles=switches)
            add(vectors.setdefault(subject, {}).setdefault(label, [0] * len(grades)), grades)
            if label == CANDIDATE:
                signals.update(SUBTYPES[event] for event in history[:-1] if event is not None)
        clear()
    for label in (refit.SETTLED, feedback.CONDITIONAL):
        if totals[label] != archived['policies'][label]:
            raise ValueError('Both sealed feedback and settled references must reproduce')
    spend = totals[CANDIDATE]['paidLookups']
    controls = refit.parent.compare_simple(plan, panels, simple, spend, vectors)
    bounds, anchors = refit.parent.compare_native(
        plan, panels, gepa, spend, simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], vectors,
    )
    paired = refit.native.frozen.paired_effects.paired_effect
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'reachableRejections': signals,
            'nativeBoundsAtCost': bounds, 'nativeAnchors': anchors, 'simpleAtCost': controls,
            'paired': {peer: paired(vectors, CANDIDATE, peer, plan)
                       for peer in (refit.SETTLED, feedback.CONDITIONAL, *controls, *anchors)}}


def verify():
    transfer = refit.transfer
    plan, context, baseline = refit.contract()
    if version('gepa') != plan['gepaVersion'] or plan['cycles'] != 3:
        raise ValueError('Use the pinned GEPA version and three-cycle archive')
    frozen = json.loads(transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    receipt = json.loads(transfer.read_locked('docs/settled-episode-qualification-feedback-v1.json', prior_api.FEEDBACK_SHA))
    for source, checksum in receipt['sourceSha256'].items():
        transfer.read_locked(source, checksum)
    parent = receipt['discovery']['policies'][feedback.CONDITIONAL]
    if any(trigger != 'finalist-rejected' for _, trigger, _ in parent['rules']):
        raise ValueError('Use the frozen rejection feedback table')
    reference = tuple((base, replacement, replacement) for base, _, replacement in parent['rules'])
    groups, models, static = refit.discovery.training(context[2])
    fit = discovery(plan, groups, models, static, reference, parent['points'])
    tables = {refit.SETTLED: tuple((base,) * 3 for base, _, _ in reference),
              feedback.CONDITIONAL: reference, CANDIDATE: fit['rules']}
    targets = {}
    for cohort in refit.discovery.COHORTS:
        target, (panels, models, static, gepa, simple, _) = refit.target(cohort, plan, context, baseline, frozen)
        name = cohort.lower()
        archived = json.loads(transfer.read_locked(
            f'docs/settled-episode-refit-transfer-{name}-v1.json', parity.LOCKS[name],
        ))
        if digest(target) != archived['planSha256'] or digest(archived['plan']) != archived['planSha256']:
            raise ValueError('Use the sealed layout and native controls')
        targets[cohort] = target_replay(
            target, panels, models, static, gepa, simple, tables, receipt['archivedTransfer'][cohort],
        )
    return {'protocol': 'settled-episode-paired-loss-feedback-v1',
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'parentFeedbackSha256': prior_api.FEEDBACK_SHA, 'transferReceiptSha256': parity.LOCKS,
            'reference': parent['points'], 'discovery': fit, 'archivedTransfer': targets, 'providerRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a fresh receipt path')
    result = verify()
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
