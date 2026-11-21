"""Bound the held-out gains available in the full fixed math rosters."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import recorded_calibrated_training_route as prior
from cpo._contract import digest


parent, transfer, math, core = prior.parent, prior.transfer, prior.math, prior.core
REFERENCE = 'docs/recorded-calibrated-training-route-results-v1.json'
REFERENCE_SHA256 = '1bbe3cd66272b46c638b7dfa698361e0257c369b545086394f9a63c1c21d193d'
QUALIFIED = 'qualification'
VALIDATED = 'validation-and-qualification'
TRAINED = 'validation-training-and-qualification'
GATES = (QUALIFIED, VALIDATED, TRAINED)
ANCHORS = (core.FIRST, prior.NEVER)
LOOKUPS = 'paidLookups'


@dataclass(frozen=True)
class Cost:
    lookups: int
    price: int

    def __add__(self, other):
        return Cost(self.lookups + other.lookups, self.price + other.price)


def charge(cells, prompt, case):
    price = cells[prompt][case][1]
    return 0 if price is None else price


def certificate_floor(cells, incumbent, challenger, rows, prefix):
    """Price the cheapest sufficient replies when all future grades are known."""
    needed = len(rows) + 1 - sum(not passed for passed in prefix.values())
    helpful = [charge(cells, incumbent, case) for case in rows
               if case not in prefix and cells[incumbent][case][0] == 0]
    helpful += [charge(cells, challenger, case) for case in rows if cells[challenger][case][0] == 1]
    if len(helpful) < needed:
        return None
    return Cost(needed, sum(sorted(helpful)[:needed]))


def offers(cells, incumbent, roster, cohorts, cap):
    training, validation, qualification, heldout = cohorts
    training = training[:len(training) // 2]
    prefix = {}
    for case in qualification:
        prefix[case] = bool(cells[incumbent][case][0])
        if not prefix[case]:
            break
    precheck = Cost(len(prefix), sum(charge(cells, incumbent, case) for case in prefix))
    old_score = sum(cells[incumbent][case][0] for case in heldout)
    heldout_gains = {prompt: sum(cells[prompt][case][0] for case in heldout) - old_score for prompt in roster}
    result = {gate: {incumbent: (0, precheck)} for gate in GATES}
    validation_target = sum(cells[incumbent][case][0] for case in validation) + 1
    base_cost = sum(charge(cells, incumbent, case) for case in validation)
    for prompt, gain in heldout_gains.items():
        qualify = certificate_floor(cells, incumbent, prompt, qualification, prefix)
        if qualify is None:
            continue
        result[QUALIFIED][prompt] = gain, precheck + qualify
        passed = sorted(charge(cells, prompt, case) for case in validation if cells[prompt][case][0])
        if len(passed) < validation_target:
            continue
        validate = Cost(len(validation) + validation_target, base_cost + sum(passed[:validation_target]))
        if validate.lookups > cap:
            continue
        result[VALIDATED][prompt] = gain, precheck + qualify + validate
        train = certificate_floor(cells, incumbent, prompt, training, {})
        if train is not None and validate.lookups + train.lookups <= cap:
            result[TRAINED][prompt] = gain, precheck + qualify + validate + train
    return old_score, max(0, max(heldout_gains.values(), default=0)), result


def extend(frontier, menu):
    """Extend the gain-to-minimum-cost frontier by exactly one episode."""
    costs = {}
    for gain, price in frontier.items():
        for extra_gain, extra_price in menu:
            score, spend = gain + extra_gain, price + extra_price
            if score not in costs or spend < costs[score]:
                costs[score] = spend
    efficient = {}
    best_cost = None
    for gain, cost in sorted(costs.items(), reverse=True):
        if best_cost is None or cost < best_cost:
            efficient[gain] = best_cost = cost
    return efficient


def summarize(frontier, start_score, budget, gepa_score):
    maximum = max(frontier)
    affordable = max(gain for gain, cost in frontier.items() if cost <= budget)
    target_cost = min((cost for gain, cost in frontier.items() if start_score + gain > gepa_score), default=None)
    return {'unconstrainedCeilingPasses': start_score + maximum, 'minimumCostAtCeiling': frontier[maximum],
            'ceilingPassesWithinBudget': start_score + affordable, 'costAtBudgetedCeiling': frontier[affordable],
            'minimumCostToBeatMatchedGEPA': target_cost}


def prepare():
    inherited, data, _, anchors, _, _ = prior.prepare()
    receipt = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion')}, 'protocol': 'recorded-math-roster-ceiling-v1',
            'parentPlanSha256': digest(inherited), 'parentReceiptSha256': REFERENCE_SHA256,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'budgetAnchors': ANCHORS,
            'gates': GATES, 'scope': 'Price the minimum exact certificates for every archived challenger '
                                   'under three nested gate sets. Charge the incumbent qualification prefix '
                                   'on every trial and full incumbent validation for validation-gated moves. '
                                   'Give hindsight access to all held-out grades, probe outcomes, and prices. '
                                   'Buy no evidence for unselected candidates. Allow cost pooling across the '
                                   'fixed trial schedule with exact gain-to-cost frontiers. Attribute the '
                                   'gate-matched gap to avoiding harmful moves and finding better nominees.'}
    return plan, data, anchors, receipt['results']


def compare_published(args, menu, evaluations, headroom):
    replayed = (core.trial(*args, core.FIRST), prior.run_trial(*args, ())[:3])
    for anchor, (point, trace, _) in zip(ANCHORS, replayed, strict=True):
        gate = TRAINED if anchor == core.FIRST else VALIDATED
        gain, floor = menu[gate][trace[3]]
        if (floor.lookups > point[LOOKUPS] or floor.price > point.get(transfer.HISTORICAL, 0)):
            raise ValueError('An actual proof cannot cost less than its optimistic certificate floor')
        evaluations[anchor].update(point)
        better_nominee = max(candidate_gain for candidate_gain, _ in menu[gate].values()) - max(gain, 0)
        headroom[anchor].update(passesFromAvoidingHarmfulMoves=max(0, -gain),
                                passesFromBetterNominees=better_nominee,
                                harmfulMoveTrials=int(gain < 0), trialsWithBetterNominee=int(better_nominee > 0))


def check_control(cells, settings, group, width, name, anchor):
    mode, _, cap = name.partition('/')
    total = Counter()
    for start, roster, cohorts, seed in transfer.trials(cells, settings, group, width):
        if name == transfer.RETAIN:
            total['holdoutPasses'] += sum(cells[start][case][0] for case in cohorts[-1])
        else:
            point, _, _ = transfer.cost.run((cells, start, roster, cohorts, seed), mode, int(cap))
            total.update(point)
    if any(total[key] != count for key, count in anchor.items()):
        raise ValueError('The cost-matched native GEPA endpoint no longer reproduces')


def measure(plan, cells, settings, group, width, certificate, no_training):
    metrics = {LOOKUPS: 'lookups'}
    if next(iter(cells.values()))[0][1] is not None:
        metrics[transfer.HISTORICAL] = 'price'
    evaluation = {arm: Counter() for arm in ANCHORS}
    headroom_by_arm = {arm: Counter() for arm in ANCHORS}
    frontiers = {metric: {gate: {0: 0} for gate in GATES} for metric in metrics}
    start_score, unrestricted_gain, trials = 0, 0, 0
    eligibility = {gate: Counter() for gate in GATES}
    for start, roster, cohorts, seed in transfer.trials(cells, settings, group, width):
        args = cells, start, roster, cohorts, seed, plan['searchCap']
        held, headroom, menu = offers(cells, start, roster, cohorts, plan['searchCap'])
        compare_published(args, menu, evaluation, headroom_by_arm)
        start_score += held
        unrestricted_gain += headroom
        trials += 1
        for gate, candidates in menu.items():
            improving = sum(gain > 0 for gain, _ in candidates.values())
            eligibility[gate].update(admissibleCandidates=len(candidates) - 1,
                                     usefulCandidates=improving, trialsWithUsefulCandidate=int(improving > 0))
            for metric, cost_field in metrics.items():
                options = {(gain, getattr(cost, cost_field)) for gain, cost in candidates.values() if gain >= 0}
                frontiers[metric][gate] = extend(frontiers[metric][gate], options)

    reported = {core.FIRST: certificate['totals'][core.FIRST], prior.NEVER: no_training['totals'][prior.NEVER]}
    controls = {core.FIRST: {key: row[core.FIRST] for key, row in certificate['comparisons'].items()},
                prior.NEVER: no_training['comparisons']}
    for arm, gate in zip(ANCHORS, (TRAINED, VALIDATED), strict=True):
        headroom = headroom_by_arm[arm]
        total_gap = start_score + max(frontiers[LOOKUPS][gate]) - reported[arm]['holdoutPasses']
        if total_gap != headroom['passesFromAvoidingHarmfulMoves'] + headroom['passesFromBetterNominees']:
            raise ValueError('The deployment attribution must reconcile to the gate-matched ceiling')
    benchmarks, verified = {}, set()
    for metric, front in frontiers.items():
        benchmarks[metric] = {}
        for arm, comparisons in controls.items():
            if any(evaluation[arm][key] != value for key, value in reported[arm].items()):
                raise ValueError('The measured CPO endpoint no longer matches the sealed receipt')
            control = comparisons[metric]
            name, point = control['bestWithinCost'], control['bestWithinCostPoint']
            if name not in verified:
                check_control(cells, settings, group, width, name, point)
                verified.add(name)
            budget = reported[arm][metric]
            benchmarks[metric][arm] = {'budget': budget, 'cpoPasses': reported[arm]['holdoutPasses'],
                                       'matchedControl': name, 'matchedControlPasses': point['holdoutPasses'],
                                       'bounds': {gate: summarize(costs, start_score, budget, point['holdoutPasses'])
                                                  for gate, costs in front.items()}}
    return {'trials': trials, 'startPasses': start_score, 'unrestrictedRosterCeiling': start_score + unrestricted_gain,
            'eligibility': eligibility, 'budgets': benchmarks, 'gateMatchedHeadroom': headroom_by_arm}


def replay(plan, data, anchors, receipt):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = measure(plan, cells, settings, group, width, anchors[dataset][name],
                                                 receipt[dataset][name])
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
