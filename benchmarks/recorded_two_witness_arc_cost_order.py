"""Test paid cost-aware validation in the qualification-first ARC policy."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from statistics import median_low
from unittest.mock import patch

from benchmarks import recorded_two_witness_math_transfer as math_transfer
from cpo._contract import digest


cost = math_transfer.cost
core = math_transfer.core
math = core.math
BASELINE = core.prior.CANDIDATE
COST_ORDERED = 'qualification-first-with-cost-ordered-validation'
METHODS = (COST_ORDERED, BASELINE, core.FIRST)
REFERENCE = 'docs/recorded-two-witness-math-transfer-results-v1.json'
REFERENCE_SHA256 = 'd57c607ac841a924b10bda6337429743e2a7273a14c260127bb69ff0805e2903'


def prepare():
    previous, data, old_controls = math_transfer.prepare()
    reference = cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, previous)
    plan = {**{key: previous[key] for key in ('gepaVersion', 'bootstrapSeed', 'bootstrapDraws', 'searchCap',
                                              'incumbentGroups', 'challengerCounts')},
            'protocol': 'recorded-two-witness-arc-cost-order-v1', 'parentPlanSha256': digest(previous),
            'parentReceiptSha256': REFERENCE_SHA256, 'dataset': previous['datasets']['arc'], 'methods': METHODS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Keep the qualification-first policy and its backup and training rules. Reorder each '
                     'full validation challenge by paid failure frequency per observed price, adding two '
                     'prior observations in the direction of the exact current leader on each case. '
                     'Verify the exact validation winner on every trial and report movement in deployment, '
                     'cost and quality against the frozen ARC GEPA cost frontiers.'}
    return plan, data['arc']['record'], old_controls['arc'], reference['results']['arc']


def select_by_paid_cost(incumbent, candidates, rows, evaluate, *, cap):
    if cap < len(rows):
        raise ValueError('Validation requires a funded incumbent panel')
    failures, prices, visits = Counter(), Counter(), Counter()
    paid = 0

    def read(prompt, row):
        nonlocal paid
        passed, charge = evaluate(prompt, row)
        if type(passed) is not bool or type(charge) is not int or charge < 0:
            raise ValueError('Validation needs a boolean grade and nonnegative integer charge')
        failures[row.id] += not passed
        prices[row.id] += charge
        visits[row.id] += 1
        paid += 1
        return passed

    leader = incumbent
    best = {row.id for row in rows if read(incumbent, row)}
    protected = {row.id for row in rows if row.critical and row.id in best}
    prior_price = max(1, median_low(prices.values()))

    def priority(row):
        miss_prior = 1 + 2 * (row.id not in best)
        chance = Fraction(failures[row.id] + miss_prior, visits[row.id] + 4)
        price = Fraction(prices[row.id] + prior_price, visits[row.id] + 1)
        return row.id not in protected, -chance / price

    for challenger in candidates:
        if len(best) == len(rows) or paid + len(rows) > cap:
            break
        passes = set()
        for index, row in enumerate(sorted(rows, key=priority), 1):
            if read(challenger, row):
                passes.add(row.id)
            elif row.id in protected:
                break
            if len(passes) + len(rows) - index <= len(best):
                break
        else:
            leader, best = challenger, passes
    return leader, paid


def run_trial(cells, start, roster, cohorts, seed, cap, *, priced):
    original_select = math.select
    nominee = start

    def choose(incumbent, candidates, rows, observe, ledger, *, method, cap):
        nonlocal nominee
        if not priced:
            nominee, tied = original_select(incumbent, candidates, rows, observe, ledger, method=method, cap=cap)
            return nominee, tied

        def evaluate(prompt, row):
            reply = observe(prompt, row)
            return reply.passed, cells[prompt][int(row.id)][1]

        nominee, calls = select_by_paid_cost(incumbent, candidates, rows, evaluate, cap=cap)
        if calls != len(ledger):
            raise ValueError('Validation price order must reconcile with paid calls')
        return nominee, False

    with patch.object(math, 'select', choose):
        point, trace, grades = core.parent.run_trial(cells, start, roster, cohorts, seed, cap,
                                                     BASELINE, core.parent.EXPECTED)
    return point, trace, grades, nominee


def paired_paths(plan, cells, group, width, totals):
    effect = Counter()
    for start, roster, cohorts, seed in math_transfer.trials(cells, plan['dataset'], group, width):
        args = (cells, start, roster, cohorts, seed, plan['searchCap'])
        before, before_trace, old_grades, old_nominee = run_trial(*args, priced=False)
        after, after_trace, new_grades, nominee = run_trial(*args, priced=True)
        if old_nominee != nominee:
            raise ValueError('Paid cost ordering changed the exact validation winner')
        delta = sum(new_grades) - sum(old_grades)
        effect.update(trials=1, changedDeployments=int(before_trace[3] != after_trace[3]),
                      holdoutPassDelta=delta, grossPassGain=max(0, delta), grossPassLoss=max(0, -delta),
                      savedLookups=before['paidLookups'] - after['paidLookups'],
                      savedHistoricalCostNanodollars=before[math_transfer.HISTORICAL] - after[math_transfer.HISTORICAL])
    if (effect['holdoutPassDelta'] != totals[COST_ORDERED]['holdoutPasses'] - totals[BASELINE]['holdoutPasses']
            or effect['savedLookups'] != totals[BASELINE]['paidLookups'] - totals[COST_ORDERED]['paidLookups']
            or effect['savedHistoricalCostNanodollars']
            != totals[BASELINE][math_transfer.HISTORICAL] - totals[COST_ORDERED][math_transfer.HISTORICAL]):
        raise ValueError('The paired audit must reconcile with the matched-cost replay')
    return effect


def replay(plan, record, controls, reference):
    cells = math.load_cells('arc', record)

    def trial(*args):
        return run_trial(*args[:-1], priced=True)[:3]

    results = {}
    for group in plan['incumbentGroups']:
        for width in plan['challengerCounts']:
            name = f'{group}/{width}'
            with (patch.object(math_transfer, 'PRIMARY', COST_ORDERED), patch.object(math_transfer, 'METHODS', METHODS),
                  patch.object(math_transfer.parity.shortlist, 'trial', trial)):
                result = math_transfer.measure(plan, cells, plan['dataset'], group, width, controls[name])
            prior = reference[name]
            if (any(point != prior['totals'][arm] for arm, point in result['totals'].items() if arm != COST_ORDERED)
                    or any(result['comparisons'][accounting][BASELINE] != previous[BASELINE]
                           for accounting, previous in prior['comparisons'].items())):
                raise ValueError('The frozen ARC scores, prices, and baseline comparisons must reproduce')
            results[name] = {**result, 'pairedValidationWinners': paired_paths(plan, cells, group, width, result['totals'])}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, record, controls, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, record, controls, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
