"""Fit episode-wide search choices from a paid opening training prefix."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import language_roster_budget_frontier as frontier
from cpo._contract import digest
from cpo.episode_probe import observe_training_prefix


bounded, discovery, depth = frontier.bounded, frontier.discovery, frontier.depth
parent, native, transfer = frontier.parent, frontier.native, frontier.transfer
BOUNDED, ROUTER, RETAIN = frontier.BOUNDED, frontier.ROUTER, frontier.RETAIN
FIXED = 'no-probe'
MODES = {FIXED: (0, False), 'incumbent-one': (1, False), 'incumbent-two': (2, False),
         'paired-one': (1, True), 'paired-two': (2, True)}
LOCKS = dict(zip(discovery.COHORTS, (
    'e100739ef1fd2b86726bd81b6afc975850d753c426af671aa07d62c83f3be89e',
    'b1eb8c699256b9fc83b69b67df12b1f2a6cd3570f12a0210c842f76c36f14925',
    'f6ea2df8421c69d7d43013f1c09866bf676648ba5f11e90af53f0565b695bca1',
    'c72d113efbbd5f39a413b0abe1c13877dad54aa8f0de7a97ff574375b22c11db',
    '3872cbf6b5246a735966e0788312333ae44df5068341304c1da02942cf2ed1bd',
    'eec0928958823f76345ed88a7aabba27ace44c597eab03533ee0c6add203df7a',
    '8adbf01ae91d97cce71c7f3f82a17872299718feca730c530f2127918d8c2961',
), strict=True))


def contract():
    previous, base, _, _, _ = bounded.contract()
    old = json.loads(transfer.read_locked('docs/bounded-opening-repair-fit-v1.json', frontier.OLDER_FIT_SHA))
    if old['planSha256'] != digest(previous) or digest(old['plan']) != old['planSha256']:
        raise ValueError('The original bounded opening must reproduce')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), Path(frontier.__file__), root / 'cpo/episode_probe.py')
    plan = {**previous, 'protocol': 'episode-training-probe-fit-v1',
            'actions': {BOUNDED: old['selected']}, 'probeModes': MODES, 'minSubjectsPerState': 3,
            'singleCandidateValidationRows': (),
            'sourceSha256': {**previous['sourceSha256'],
                             **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}},
            'scope': 'Buy one or two incumbent grades or same-case pairs at the start of an episode. '
                     'Choose one setting for all three cycles using only a paid opening training summary. '
                     'Enumerate every supported state-to-action table under the realized bounded opening '
                     'budget per discovery cohort. Use the same quoted schedule menu as the roster frontier. '
                     'Keep validation and qualification wholly separate, and charge every probe.'}
    return plan, base, old


def episodes(plan, panels):
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        for seed in plan['seeds']:
            start, stages = depth.continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            yield subject, model, seed, cells, stages, start


def probe(mode, modes, cells, stages, start):
    _, candidates, roles = stages[0]
    count, paired = modes[mode]
    ledger = []

    def observe(prompt, case):
        grade = bool(cells[prompt][case])
        ledger.append((prompt, case, grade))
        return grade

    state = observe_training_prefix(start, candidates, roles[0], observe, count=count, paired=paired)
    if len(ledger) != count * (1 + paired):
        raise ValueError('The probe must charge every training reply exactly once')
    return state, ledger


def fit_table(observations, options, budgets, min_subjects):
    names = tuple(budgets)
    states, support = {}, {}
    for cohort, subject, state, probe_cost, deck in observations:
        support.setdefault(state, set()).add(subject)
        table = states.setdefault(state, {name: {label: Counter() for label in options} for name in names})
        for label, point in deck.items():
            table[cohort][label].update(passes=point.passes, lookups=point.cost + probe_cost)
    ordering = sorted(states)
    menu = [options if len(support[state]) >= min_subjects else (RETAIN,) for state in ordering]
    indexed = [{label: tuple((states[state][cohort][label]['passes'], states[state][cohort][label]['lookups'])
                              for cohort in names) for label in labels} for state, labels in zip(ordering, menu)]
    best, best_table, feasible = None, None, 0
    for actions in product(*menu):
        points = [table[label] for table, label in zip(indexed, actions, strict=True)]
        prices = tuple(sum(part[1] for part in cohort) for cohort in zip(*points))
        if any(price > budgets[cohort] for price, cohort in zip(prices, names, strict=True)):
            continue
        feasible += 1
        quality = tuple(sum(part[0] for part in cohort) for cohort in zip(*points))
        rank = -sum(quality), sum(prices), actions
        if best is None or rank < best:
            best = rank
            best_table = {'actions': dict(zip(ordering, actions, strict=True)),
                          'points': {cohort: {'holdoutPasses': score, 'paidLookups': price}
                                     for cohort, score, price in zip(names, quality, prices, strict=True)}}
    if best_table is None:
        raise ValueError('No fitted table can afford the probes within the cohort budgets')
    return {**best_table, 'feasibleTables': feasible,
            'support': {state: len(subjects) for state, subjects in support.items()}}


def fit(plan, groups, models, static, old):
    fixed, singles = frontier.engines(plan, models, static)
    data = {mode: [] for mode in plan['probeModes']}
    budgets = {name: record['paidLookups'] for name, record in old['policies'][BOUNDED]['byCohort'].items()}
    baseline = {cohort: Counter() for cohort in budgets}
    for cohort in budgets:
        eligible = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in eligible]
        for subject, _, _, cells, stages, start in episodes(plan, panels):
            rollout, _, clear = frontier.episode_model(plan, cells, stages, fixed, singles)
            deck = {label: rollout(start, (label,) * len(stages))[0] for label in fixed}
            clear()
            reference = deck[BOUNDED]
            baseline[cohort].update(holdoutPasses=reference.passes, paidLookups=reference.cost)
            for mode in data:
                state, ledger = probe(mode, plan['probeModes'], cells, stages, start)
                data[mode].append((cohort, subject, state, len(ledger), deck))
    if baseline != old['policies'][BOUNDED]['byCohort']:
        raise ValueError('The bounded opening discovery score and price must reproduce')
    fits = {mode: fit_table(rows, tuple(sorted(fixed)), budgets, plan['minSubjectsPerState'])
            for mode, rows in data.items()}
    points = {BOUNDED: baseline, **{mode: table['points'] for mode, table in fits.items()}}
    winner = min(points, key=lambda name: (depth.rank(points[name]), name != BOUNDED, name))
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'selected': winner, 'fits': fits, 'baseline': baseline, 'budgets': budgets}


def target(cohort, plan, fitted):
    if fitted['planSha256'] != digest(plan) or digest(fitted['plan']) != digest(plan):
        raise ValueError('Use the sealed discovery fit')
    inherited, inputs = frontier.prepare(cohort)
    lock = LOCKS[cohort]
    old = json.loads(transfer.read_locked(f'docs/language-roster-budget-frontier-{cohort.lower()}-v1.json', lock))
    if old['planSha256'] != digest(inherited):
        raise ValueError('The same language episodes and roster frontier must reproduce')
    tables = {name: entry['actions'] for name, entry in fitted['fits'].items()}
    target_plan = {**inherited, 'protocol': 'episode-training-probe-transfer-v1',
                   'fitSha256': digest(fitted), 'frontierReceiptSha256': lock, 'selectedPolicy': fitted['selected'],
                   'trainedActions': tables, 'probeModes': plan['probeModes'], 'singleCandidateValidationRows': (),
                   'sourceSha256': {**inherited['sourceSha256'], **plan['sourceSha256']},
                   'scope': 'Buy exactly the fitted opening prefix and run its chosen fixed setting across '
                            'the three cycles. Verify the bounded opening and compare the fixed no-probe '
                            'fit and the four probe policies at measured spend.'}
    return target_plan, (*inputs[:-1], old['results'])


def replay(plan, panels, models, static, gepa, simple, prior):
    fixed, singles = frontier.engines(plan, models, static)
    names = (BOUNDED, *plan['probeModes'])
    tables = plan['trainedActions']
    totals = {name: Counter() for name in names}
    choices = {name: Counter() for name in names}
    vectors, baseline_paths = {}, {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, model, seed, cells, stages, start in episodes(plan, panels):
        rollout, _, clear = frontier.episode_model(plan, cells, stages, fixed, singles)
        held = stages[0][2][-1]
        scores = vectors.setdefault(subject, {})
        for name in names:
            if name == BOUNDED:
                action, ledger = name, []
            else:
                state, ledger = probe(name, plan['probeModes'], cells, stages, start)
                action = tables[name].get(state, RETAIN)
            point, trace = rollout(start, (action,) * len(stages))
            if name == BOUNDED:
                baseline_paths.setdefault(f'{subject}/{model}', []).append(trace)
            current = trace[-1][1] if trace else start
            grades = [cells[current][case] for case in held]
            if sum(grades) != point.passes:
                raise ValueError('Every routed deployment must attain its recorded holdout score')
            add(scores.setdefault(name, [0] * len(held)), grades)
            totals[name].update(holdoutPasses=point.passes, paidLookups=point.cost + len(ledger),
                                trainingLookups=len(ledger))
            choices[name][action] += 1
        clear()
    if (totals[BOUNDED] != {**prior['baseline'], 'trainingLookups': 0}
            or any(digest(paths) != prior['baselineTrajectoryHashes'][key][BOUNDED]
                   for key, paths in baseline_paths.items())):
        raise ValueError('The bounded opening and all its paid paths must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name in plan['probeModes']:
        spend = totals[name]['paidLookups']
        grades = {subject: dict(values) for subject, values in vectors.items()}
        controls = parent.compare_simple(plan, panels, simple, spend, grades)
        bounds, anchors = parent.compare_native(plan, panels, gepa, spend,
                                                 simple['settingsTotals'][RETAIN]['holdoutPasses'], grades)
        peers = (BOUNDED,) if name == FIXED else (BOUNDED, FIXED)
        comparisons[name] = {'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors, 'simpleAtBudget': controls,
                             'withinBoundedBudget': spend <= prior['budget'],
                             'paired': {other: paired(grades, name, other, plan)
                                        for other in (*peers, *controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'selectedSchedules': choices,
            'comparisons': comparisons, 'sameBudgetEpisodeFrontier': prior['frontiers'][frontier.EPISODE]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument('--fit', action='store_true')
    phase.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, base, old = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, inputs = target(args.cohort, plan, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, models, static = discovery.training(base)
        report = fit(plan, groups, models, static, old)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
