"""Order exact training proofs by estimated remaining lookup cost."""

import argparse
from collections import Counter
from functools import lru_cache
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_two_witness_math_transfer as math_transfer
from cpo._contract import digest
from cpo.expected_qualification import _pass_rate


core, cost, math = math_transfer.core, math_transfer.cost, math_transfer.math
BASELINE = core.prior.CANDIDATE
ORDERED = 'qualification-first-expected-training-order'
METHODS = (ORDERED, BASELINE, core.FIRST)
REFERENCE = 'docs/recorded-two-witness-math-transfer-results-v1.json'
REFERENCE_SHA256 = 'd57c607ac841a924b10bda6337429743e2a7273a14c260127bb69ff0805e2903'


@lru_cache(maxsize=100_000)
def next_side(rates, prices, remaining, needed):
    """Return scaled expected cost and the next side under the fixed estimates."""
    left = sum(remaining)
    if needed <= 0 or needed > left:
        return 0, None
    options = []
    for side, unread in enumerate(remaining):
        if not unread:
            continue
        following = (remaining[0] - (side == 0), remaining[1] - (side == 1))
        fail = next_side(rates, prices, following, needed)[0]
        hit = next_side(rates, prices, following, needed - 1)[0]
        value = prices[side] * 4**left + (4 - rates[side]) * fail + rates[side] * hit
        options.append((value, side))
    return min(options)


def settle(prompts, rows, observe, ledger, rates, prices, *, minimum_gain):
    needed = len(rows) + minimum_gain
    pending = ([], [])
    for side, prompt in enumerate(prompts):
        for row in rows:
            if (prompt, row.id) in ledger:
                needed -= ledger[prompt, row.id].passed == bool(side)
            else:
                pending[side].append(row)
    remaining = tuple(map(len, pending))
    while 0 < needed <= sum(remaining):
        _, side = next_side(rates, prices, remaining, needed)
        row = pending[side][len(pending[side]) - remaining[side]]
        grade = observe(prompts[side], row).passed
        if type(grade) is not bool:
            raise ValueError('Training requires exact boolean grades')
        needed -= grade == bool(side)
        remaining = (remaining[0] - (side == 0), remaining[1] - (side == 1))
    return needed <= 0


def estimate(prompts, rows, ledger, cells):
    evidence = [[(row.id, ledger[prompt, row.id].passed) for row in rows if (prompt, row.id) in ledger]
                for prompt in prompts]
    old_rate, new_rate = (_pass_rate(sum(passed for _, passed in replies), len(replies)) for replies in evidence)
    prices = [[price for case, _ in replies if (price := cells[prompt][int(case)][1]) is not None]
              for prompt, replies in zip(prompts, evidence, strict=True)]
    observed = [price for grades in prices for price in grades]
    fallback = max(1, sum(observed) // len(observed)) if observed else 1
    means = tuple(max(1, sum(grades) // len(grades)) if grades else fallback for grades in prices)
    return (4 - old_rate, new_rate), means


def run_trial(cells, start, roster, cohorts, seed, cap):
    backup = core.backup
    original_select, original_proof = backup.select_with_training, backup.prior.corroborate

    def select(incumbent, first, candidates, validation, training, observe, ledger, **options):
        def prove(old, new, rows, evaluate, *, minimum_gain, remaining, seed):
            if remaining < 2 * len(rows):
                return original_proof(old, new, rows, evaluate, minimum_gain=minimum_gain,
                                      remaining=remaining, seed=seed)
            prompts = old, new
            rates, prices = estimate(prompts, validation, ledger, cells)
            return settle(prompts, rows, evaluate, ledger, rates, prices, minimum_gain=minimum_gain)

        with patch.object(backup.prior, 'corroborate', prove):
            return original_select(incumbent, first, candidates, validation, training, observe, ledger, **options)

    with patch.object(backup, 'select_with_training', select):
        return core.parent.run_trial(cells, start, roster, cohorts, seed, cap, BASELINE, core.parent.EXPECTED)


def prepare():
    inherited, data, controls = math_transfer.prepare()
    archived = cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-expected-training-order-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'methods': METHODS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Keep the qualification-first validation, backup, and proof thresholds. Credit cached '
                     'training outcomes and order remaining exact training replies by expected cost. Use '
                     'only paid validation to estimate rates and ARC prices, and unit cost for AIME. Verify '
                     'the original nominees and deployments per trial. Compare to the same GEPA frontiers.'}
    return plan, data, controls, archived['results']


def paired_paths(plan, cells, settings, group, width, totals):
    effect = Counter()
    for start, roster, cohorts, seed in math_transfer.trials(cells, settings, group, width):
        args = (cells, start, roster, cohorts, seed, plan['searchCap'])
        before, old_trace, old_grades = core.trial(*args, BASELINE)
        after, new_trace, new_grades = run_trial(*args)
        if old_trace[:4] != new_trace[:4] or old_grades != new_grades:
            raise ValueError('Training proof order changed an archived nominee, deployment, or held-out grade')
        saved = before['paidLookups'] - after['paidLookups']
        if (before['qualificationLookups'] != after['qualificationLookups']
                or saved != before.get('trainingLookups', 0) - after.get('trainingLookups', 0)):
            raise ValueError('Training proof order changed a non-training lookup count')
        effect.update(trials=1, savedLookups=saved, trialsCheaper=int(saved > 0), trialsDearer=int(saved < 0))
        if math_transfer.HISTORICAL in before:
            effect['savedHistoricalCostNanodollars'] += before[math_transfer.HISTORICAL] - after[math_transfer.HISTORICAL]
    if effect['savedLookups'] != totals[BASELINE]['paidLookups'] - totals[ORDERED]['paidLookups']:
        raise ValueError('The paired proof audit must reconcile with the paid totals')
    return effect


def replay(plan, data, controls, reference):
    def trial(*args):
        return run_trial(*args[:-1])

    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                with (patch.object(math_transfer, 'PRIMARY', ORDERED), patch.object(math_transfer, 'METHODS', METHODS),
                      patch.object(math_transfer.parity.shortlist, 'trial', trial)):
                    result = math_transfer.measure(plan, cells, settings, group, width, controls[dataset][name])
                prior = reference[dataset][name]
                if (any(point != prior['totals'][arm] for arm, point in result['totals'].items() if arm != ORDERED)
                        or any(result['comparisons'][accounting][BASELINE] != previous[BASELINE]
                               for accounting, previous in prior['comparisons'].items())):
                    raise ValueError('The original policy and GEPA frontiers must reproduce')
                results[dataset][name] = {**result, 'pairedTrainingProofs':
                                          paired_paths(plan, cells, settings, group, width, result['totals'])}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, controls, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, data, controls, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
