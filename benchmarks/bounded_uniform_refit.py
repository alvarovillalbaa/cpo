"""Re-fit episode schedules after lowering the cost of exact validation."""

import argparse
from collections import Counter
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import episode_training_probe_transfer as previous
from benchmarks import perfect_challenger_transfer as perfect
from cpo._contract import digest
from cpo.bounded_uniform_validation import screen
from cpo.two_sided_certificate_cycle import _run


frontier, discovery, depth = previous.frontier, previous.discovery, previous.depth
native, parent, transfer = previous.native, previous.parent, previous.transfer
BOUNDED, RETAIN = previous.BOUNDED, previous.RETAIN
MODES = (previous.FIXED, 'incumbent-two')
FIT_SHA = '930f88592246fe56cb1bc2da745cc924cd06250d537548d4ef3422a0ce8ef4d5'
LOCKS = dict(zip(discovery.COHORTS, (
    '24fcba7b106b0249252a494e965e10eeb88d80e5e8160e2f8de5b43ca590405e',
    '2824762a2d0fbbd4b3033448a98921e7c13133fb96a29da1b57d018959f13f27',
    'c0876dc54b053a1d8f08b10095b6d4c715479c5a9092b0776062676a6b521f17',
    '8387d80d13f13a7e7068b2d2d8d54ba73c4fe16a81848827b0e288ab450b99f1',
    '364e4a0120b2b656a0c44cf651940e8ba5c3264fd10701b469f94bb34fee9f44',
    '13929e2a4ff73a57f2a7adae41fd9b437d30bbe6aa16ae1d9b4332da19a032e1',
    '9dfe948f8179ea6c02049b6dea952bfad3b1b29eeb127a0d6d5b9a5b060c3fea',
), strict=True))


def contract():
    inherited, base, _ = previous.contract()
    old = json.loads(transfer.read_locked('docs/episode-training-probe-fit-v1.json', FIT_SHA))
    if digest(inherited) != old['planSha256'] or digest(old['plan']) != old['planSha256']:
        raise ValueError('The original episode fit must reproduce')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), Path(perfect.__file__), root / 'cpo/perfect_challenger_screen.py',
             root / 'cpo/bounded_uniform_validation.py')
    plan = {**inherited, 'protocol': 'bounded-uniform-refit-v1', 'previousFitSha256': FIT_SHA, 'refitModes': MODES,
            'sourceSha256': {**inherited['sourceSha256'],
                             **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}},
            'scope': 'Price unchanged uniform and successive-halving decisions with ordered score bounds and '
                     'perfect-prefix reads. Verify the original discovery fit. Then refit the constant and '
                     'two-incumbent-probe tables on the same disjoint tasks and per-cohort budgets. '
                     'Compare original decisions, repriced original decisions, and the frozen refit.'}
    return plan, inherited, base, old


def limit(incumbent, candidates, rows, evaluate, cap, *, width, maximum, halve):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, maximum), halve=halve)


def engines(plan, models, static):
    original, _ = frontier.engines(plan, models, static)
    optimized = {label: partial(_run, screen=partial(limit, width=width, maximum=cap,
                                                   halve=mode == 'successive-halving'))
                 for label, mode, width, cap in plan['controls']}
    return original, optimized


def episode(plan, cells, stages, start, original, optimized):
    cap = max(limit for _, _, _, limit in plan['controls'])
    run = native.paired.cycle.execute_path
    held = stages[0][2][-1]

    @cache
    def rollout(label):
        current, old, new = start, 0, 0
        if label == RETAIN:
            return [cells[current][row] for row in held], old, new
        for stage in stages:
            if label in optimized:
                current, before, after = perfect.compare_cycle(original[label], optimized[label],
                                                               cells, current, stage, cap)
            else:
                seed, roster, roles = stage
                decision, ledger = run(original[label], cells, current, roster, roles, seed, cap, 1)
                depth.continuous.routing.verify_qualification(cells, current, roles, decision, ledger, 1)
                current, before, after = decision.prompt, len(ledger), len(ledger)
            old += before
            new += after
        return [cells[current][row] for row in held], old, new

    return rollout


def fit(plan, groups, models, static, old):
    original, optimized = engines(plan, models, static)
    budgets = old['budgets']
    rows = {mode: [[], []] for mode in MODES}
    baseline = {cohort: Counter() for cohort in budgets}
    for cohort in budgets:
        enrolled = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in enrolled]
        for subject, _, _, cells, stages, start in previous.episodes(plan, panels):
            rollout = episode(plan, cells, stages, start, original, optimized)
            old_deck, new_deck = {}, {}
            for label in original:
                grades, before, after = rollout(label)
                passes = sum(grades)
                old_deck[label] = frontier.Point(passes, before, (label,))
                new_deck[label] = frontier.Point(passes, after, (label,))
            rollout.cache_clear()
            point = old_deck[BOUNDED]
            baseline[cohort].update(holdoutPasses=point.passes, paidLookups=point.cost)
            for mode, (before, after) in rows.items():
                state, ledger = previous.probe(mode, plan['probeModes'], cells, stages, start)
                before.append((cohort, subject, state, len(ledger), old_deck))
                after.append((cohort, subject, state, len(ledger), new_deck))
    if baseline != old['baseline']:
        raise ValueError('The bounded baseline must reproduce')
    choices, priced = {}, {}
    for mode, (before, after) in rows.items():
        arguments = tuple(sorted(original)), budgets, plan['minSubjectsPerState']
        if previous.fit_table(before, *arguments) != old['fits'][mode]:
            raise ValueError('The original table and every discovery cohort point must reproduce')
        frozen = old['fits'][mode]['actions']
        controls = {cohort: Counter() for cohort in budgets}
        for cohort, _, state, probe_cost, deck in after:
            entry = deck[frozen[state]]
            controls[cohort].update(holdoutPasses=entry.passes, paidLookups=entry.cost + probe_cost)
        priced[mode] = controls
        choices[mode] = previous.fit_table(after, *arguments)
    points = {BOUNDED: baseline, **{mode: arm['points'] for mode, arm in choices.items()}}
    winner = min(points, key=lambda name: (depth.rank(points[name]), name != BOUNDED, name))
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'selected': winner,
            'optimizedFits': choices, 'repricedOldFits': priced, 'baseline': baseline}


def target(cohort, plan, inherited, old_fit, fit_receipt):
    if fit_receipt['planSha256'] != digest(plan) or digest(fit_receipt['plan']) != digest(plan):
        raise ValueError('Use the sealed refit')
    original, inputs = previous.target(cohort, inherited, old_fit)
    lock = LOCKS[cohort]
    old = json.loads(transfer.read_locked(f'docs/episode-training-probe-transfer-{cohort.lower()}-v1.json', lock))
    if old['planSha256'] != digest(original):
        raise ValueError('The earlier episode replay must reproduce')
    target_plan = {**original, 'protocol': 'bounded-uniform-refit-transfer-v1', 'refitSha256': digest(fit_receipt),
                   'oldEpisodeTransferSha256': lock, 'selectedPolicy': fit_receipt['selected'],
                   'optimizedActions': {name: item['actions'] for name, item in fit_receipt['optimizedFits'].items()},
                   'sourceSha256': {**original['sourceSha256'], **plan['sourceSha256']},
                   'scope': 'Compare unchanged, repriced and refitted schedules with paid training reads and '
                            'affordable native and simple controls at actual total lookup prices.'}
    return target_plan, (*inputs[:-1], old['results'])


def replay(plan, panels, models, static, gepa, simple, prior):
    original, optimized = engines(plan, models, static)
    names = (BOUNDED, *(f'{name}/{arm}' for name in MODES for arm in ('old', 'repriced', 'refit')))
    totals, choices = ({name: Counter() for name in names} for _ in range(2))
    vectors = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, _, _, cells, stages, start in previous.episodes(plan, panels):
        rollout = episode(plan, cells, stages, start, original, optimized)
        chosen = {BOUNDED: (BOUNDED, 0, 1)}
        for mode in MODES:
            state, ledger = previous.probe(mode, plan['probeModes'], cells, stages, start)
            earlier = plan['trainedActions'][mode].get(state, RETAIN)
            refitted = plan['optimizedActions'][mode].get(state, RETAIN)
            chosen.update({f'{mode}/old': (earlier, len(ledger), 1),
                           f'{mode}/repriced': (earlier, len(ledger), 2),
                           f'{mode}/refit': (refitted, len(ledger), 2)})
        scores = vectors.setdefault(subject, {})
        for name, (action, probe_cost, price) in chosen.items():
            point = rollout(action)
            grades = point[0]
            totals[name].update(holdoutPasses=sum(grades), paidLookups=point[price] + probe_cost,
                                trainingLookups=probe_cost)
            choices[name][action] += 1
            add(scores.setdefault(name, [0] * len(grades)), grades)
        rollout.cache_clear()
    if totals[BOUNDED] != prior['policies'][BOUNDED]:
        raise ValueError('The bounded opening baseline must reproduce')
    for mode in MODES:
        label = f'{mode}/old'
        if totals[label] != prior['policies'][mode] or choices[label] != prior['selectedSchedules'][mode]:
            raise ValueError('The original policy score, cost and schedule choices must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for mode in MODES:
        for arm in ('repriced', 'refit'):
            name = f'{mode}/{arm}'
            pool = {subject: dict(scores) for subject, scores in vectors.items()}
            cost = totals[name]['paidLookups']
            controls = parent.compare_simple(plan, panels, simple, cost, pool)
            bounds, anchors = parent.compare_native(plan, panels, gepa, cost,
                                                     simple['settingsTotals'][RETAIN]['holdoutPasses'], pool)
            comparisons[name] = {'simpleAtBudget': controls, 'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors,
                                 'withinBoundedBudget': cost <= totals[BOUNDED]['paidLookups'],
                                 'paired': {other: paired(pool, name, other, plan)
                                            for other in (BOUNDED, f'{mode}/old', *controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'selectedSchedules': choices,
            'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inherited, base, old = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, inputs = target(args.cohort, plan, inherited, old, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, models, static = discovery.training(base)
        receipt = fit(plan, groups, models, static, old)
    else:
        receipt = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
