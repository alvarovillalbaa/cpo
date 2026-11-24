"""Isolate episode retention from wider search and price a lazy admission rule."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import episode_training_probe_transfer as previous
from cpo._contract import digest
from cpo.episode_admission import retain_after_training_prefix


frontier, discovery, depth = previous.frontier, previous.discovery, previous.depth
parent, native, transfer = previous.parent, previous.native, previous.transfer
BOUNDED, RETAIN = previous.BOUNDED, previous.RETAIN
BOTH, ADMIT, SCHEDULE = 'incumbent-two', 'retention-only-eager', 'wider-search-only'
PREFIX = {f'perfect-prefix-{count}': count for count in (1, 2, 3, 4)}
FAST_TWO = 'perfect-prefix-2'
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
        raise ValueError('The earlier episode fit must reproduce')
    table = old['fits'][BOTH]['actions']
    if table['0'] != BOUNDED or table['2'] != RETAIN or table['1'] in (BOUNDED, RETAIN):
        raise ValueError('The earlier policy must combine distinct retention and wider-search actions')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/episode_admission.py')
    plan = {**inherited, 'protocol': 'episode-admission-fit-v1', 'episodeProbeFitSha256': FIT_SHA,
            'prefixLengths': PREFIX, 'twoProbeActions': table,
            'sourceSha256': {**inherited['sourceSha256'],
                             **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}},
            'scope': 'Separate the effect of retention after two incumbent training passes from changing '
                     'the search schedule after one pass. Then keep the bounded opening on any miss, '
                     'stop the training probe as soon as that miss occurs, and fit the perfect prefix '
                     'length on the same disjoint tasks under the original per-cohort budgets.'}
    return plan, inherited, base, old


def admit(cells, stages, start, count):
    _, _, roles = stages[0]
    ledger = []

    def read(prompt, case):
        grade = bool(cells[prompt][case])
        ledger.append((prompt, case, grade))
        return grade

    keep = retain_after_training_prefix(start, roles[0], read, count=count)
    return (RETAIN if keep else BOUNDED), ledger


def actions(plan, cells, stages, start):
    state, original = previous.probe(BOTH, plan['probeModes'], cells, stages, start)
    fitted = plan['twoProbeActions']
    branches = {BOUNDED: (BOUNDED, []), BOTH: (fitted[state], original),
                ADMIT: (RETAIN if state == '2' else BOUNDED, original),
                SCHEDULE: (fitted['1'] if state == '1' else BOUNDED, original)}
    branches.update({name: admit(cells, stages, start, count) for name, count in plan['prefixLengths'].items()})
    if branches[FAST_TWO][0] != branches[ADMIT][0] or branches[FAST_TWO][1] != original[:len(branches[FAST_TWO][1])]:
        raise ValueError('Early termination must preserve the retention choice and only skip a paid suffix')
    return branches


def measure(plan, panels, models, static, vectors):
    fixed, singles = frontier.engines(plan, models, static)
    names = (BOUNDED, BOTH, ADMIT, SCHEDULE, *plan['prefixLengths'])
    totals = {name: Counter() for name in names}
    decisions = {name: Counter() for name in names}
    paths = {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, model, _, cells, stages, start in previous.episodes(plan, panels):
        branches = actions(plan, cells, stages, start)
        rollout, _, clear = frontier.episode_model(plan, cells, stages, fixed, singles)
        deck = {name: rollout(start, (name,) * len(stages)) for name in sorted({arm for arm, _ in branches.values()})}
        clear()
        held = stages[0][2][-1]
        case_scores = vectors.setdefault(subject, {})
        for name, (setting, ledger) in branches.items():
            result, trace = deck[setting]
            grades = [cells[trace[-1][1] if trace else start][case] for case in held]
            add(case_scores.setdefault(name, [0] * len(held)), grades)
            totals[name].update(holdoutPasses=result.passes, paidLookups=result.cost + len(ledger),
                                trainingLookups=len(ledger))
            decisions[name][setting] += 1
            if name == BOUNDED:
                paths.setdefault(f'{subject}/{model}', []).append(trace)

        base, combined, admission, schedule = (deck[branches[name][0]][0] for name in (BOUNDED, BOTH, ADMIT, SCHEDULE))
        if (combined.passes - base.passes != admission.passes + schedule.passes - 2 * base.passes
                or combined.cost - base.cost != admission.cost + schedule.cost - 2 * base.cost):
            raise ValueError('Retention and wider-search effects must reconcile on every episode')
    return totals, decisions, {key: digest(path) for key, path in paths.items()}


def fit(plan, groups, models, static, old):
    budgets = old['budgets']
    outcomes = {}
    for cohort in budgets:
        eligible = set(map(tuple, plan['fitEnrollment'][cohort]))
        panels = [panel for panel in groups[cohort] if panel[:2] in eligible]
        outcomes[cohort], _, _ = measure(plan, panels, models, static, {})
    for name, rows in ((BOUNDED, old['baseline']), (BOTH, old['fits'][BOTH]['points'])):
        for cohort, point in rows.items():
            if any(outcomes[cohort][name][metric] != value for metric, value in point.items()):
                raise ValueError('The original baseline and two-probe fit must reproduce')
    names = (BOUNDED, BOTH, *plan['prefixLengths'])
    candidates = {name: {cohort: point[name] for cohort, point in outcomes.items()} for name in names}
    feasible = [name for name in names
                if all(row['paidLookups'] <= budgets[cohort] for cohort, row in candidates[name].items())]
    chosen = min(feasible, key=lambda name: (depth.rank(candidates[name]), name != BOUNDED, name))
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'selectedPolicy': chosen, 'feasible': feasible, 'outcomes': outcomes, 'budgets': budgets}


def target(cohort, plan, inherited, old_fit, fitted):
    if fitted['planSha256'] != digest(plan) or digest(fitted['plan']) != digest(plan):
        raise ValueError('Use the sealed discovery fit')
    old_plan, data = previous.target(cohort, inherited, old_fit)
    lock = LOCKS[cohort]
    report = json.loads(transfer.read_locked(f'docs/episode-training-probe-transfer-{cohort.lower()}-v1.json', lock))
    if report['planSha256'] != digest(old_plan):
        raise ValueError('The earlier episode probe must use these exact layouts')
    target_plan = {**old_plan, 'protocol': 'episode-admission-transfer-v1', 'admissionFitSha256': digest(fitted),
                   'previousTransferSha256': lock, 'prefixLengths': plan['prefixLengths'],
                   'twoProbeActions': plan['twoProbeActions'], 'selectedPolicy': fitted['selectedPolicy'],
                   'sourceSha256': {**old_plan['sourceSha256'], **plan['sourceSha256']},
                   'scope': 'Check exact two-probe and no-probe replay. Measure both isolated changes '
                            'and early-stop prefixes at their true paid cost. Preserve all validation '
                            'and qualification gates, and compare affordable native and simple controls.'}
    return target_plan, (*data, report['results'])


def replay(plan, panels, models, static, gepa, simple, frontier_result, old):
    vectors = {}
    totals, decisions, paths = measure(plan, panels, models, static, vectors)
    if any(totals[name] != old['policies'][name] or decisions[name] != old['selectedSchedules'][name]
           for name in (BOUNDED, BOTH)):
        raise ValueError('Both earlier episode policies must reproduce exactly')
    if any(trace != frontier_result['baselineTrajectoryHashes'][key][BOUNDED] for key, trace in paths.items()):
        raise ValueError('Every original bounded opening paid path must reproduce')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name in (*plan['prefixLengths'], ADMIT, SCHEDULE):
        grades = {subject: dict(scores) for subject, scores in vectors.items()}
        cost = totals[name]['paidLookups']
        controls = parent.compare_simple(plan, panels, simple, cost, grades)
        bounds, anchors = parent.compare_native(plan, panels, gepa, cost,
                                                 simple['settingsTotals'][RETAIN]['holdoutPasses'], grades)
        comparisons[name] = {'simpleAtBudget': controls, 'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors,
                             'withinBoundedBudget': cost <= frontier_result['budget'],
                             'paired': {other: paired(grades, name, other, plan)
                                        for other in (BOUNDED, BOTH, *controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals,
            'decisions': decisions, 'comparisons': comparisons}


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
        report = fit(plan, groups, models, static, old)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
