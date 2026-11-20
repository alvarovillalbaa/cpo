"""Reproduce Sol charge-aware cost bounds from anonymous numeric ledgers."""

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path

from benchmarks.certified_opening_cost_sensitivity import measure as fixed_bounds


DATA = Path(__file__).with_name('data') / 'paired-field-path-charge-costs-v1.jsonl'
FIXED = DATA.with_name('paired-field-rewrite-cost-terms-v1.json')
GATE = Fraction(9, 10)
NATIVE = 'chargeAwareVersusNative'
PAIRED = 'chargeAwareVersusRowPaired'
SHARED = 'sharedChargeSavingsFraction'
SEPARATE = 'separateChargeSavingsFraction'


@dataclass(frozen=True)
class Ledger:
    opening: int
    terms: tuple

    def extreme(self, ratio, maximize, shared):
        candidate = control = self.opening
        direction = 1 if maximize else -1
        for ours, theirs, low, high in self.terms:
            if shared:
                weight = ours * ratio.denominator - theirs * ratio.numerator
                left = right = high if direction * weight > 0 else low
            else:
                left, right = (high, low) if maximize else (low, high)
            candidate += ours * left
            control += theirs * right
        return candidate, control


@dataclass(frozen=True)
class PathCosts:
    continuous: tuple
    observed: tuple
    count: int = 1

    def extreme(self, ratio, maximize, shared, continuous):
        choose = max if maximize else min
        if continuous:
            candidates = (ledger.extreme(ratio, maximize, shared) for ledger in self.continuous)
        elif shared:
            candidates = self.observed
        else:
            opposite = min if maximize else max
            return choose(row[0] for row in self.observed), opposite(row[1] for row in self.observed)
        return choose(candidates, key=lambda row: row[0] * ratio.denominator - row[1] * ratio.numerator)


def total_cost(paths, ratio, *, maximize, shared, continuous):
    candidate = control = 0
    for path in paths:
        ours, theirs = path.extreme(ratio, maximize, shared, continuous)
        candidate += path.count * ours
        control += path.count * theirs
    return candidate, control


def savings_bound(paths, *, maximize, shared, continuous):
    ratio = Fraction(1)
    while True:
        # Each path can independently extremize its contribution to
        # candidate - ratio * control. A zero sum identifies the extremum.
        candidate, control = total_cost(paths, ratio, maximize=maximize, shared=shared, continuous=continuous)
        updated = Fraction(candidate, control)
        if updated == ratio:
            return 1 - ratio
        ratio = updated


def interval(paths):
    audit = {}
    for shared, label in ((True, SHARED), (False, SEPARATE)):
        outer = [savings_bound(paths, maximize=flag, shared=shared, continuous=True) for flag in (True, False)]
        witnessed = [savings_bound(paths, maximize=flag, shared=shared, continuous=False) for flag in (True, False)]
        if not outer[0] <= witnessed[0] <= witnessed[1] <= outer[1]:
            raise ValueError('The interval excludes a recorded-price witness')
        audit[label] = list(map(str, outer))
        audit[label + 'ObservedWitnesses'] = list(map(str, witnessed))
        audit[label + 'IsTight'] = outer == witnessed
    return audit


def headroom(paths, row_paired):
    charged, native = total_cost(paths, GATE, maximize=True, shared=False, continuous=True)
    margin = native * GATE - charged
    witnessed = total_cost(paths, GATE, maximize=True, shared=False, continuous=False)
    fixed_lower = Fraction(row_paired[SEPARATE][0])
    fixed_margin = native * (GATE - (1 - fixed_lower))
    return {'chargeAwareOnlyAdditionalMicrousd': str(margin),
            'sharedAdditionalOpeningMicrousd': str(margin / (1 - GATE)),
            'worstCaseChargeAwareMicrousd': charged, 'worstCaseNativeMicrousd': native,
            'rowPairedOnlyAdditionalMicrousd': str(fixed_margin),
            'additionalMarginVersusRowPairedMicrousd': str(margin - fixed_margin),
            'observedPricesAttainTheBound': (charged, native) == witnessed}


def verify_solver():
    paths = (
        PathCosts((Ledger(10, ((1, 1, 2, 3), (0, 1, 4, 7))),
                   Ledger(10, ((0, 1, 2, 3), (1, 1, 4, 7)))), ()),
        PathCosts((Ledger(20, ((1, 1, 3, 8), (0, 1, 2, 5))),), ()),
    )
    counts = {}
    for shared, label in ((True, SHARED), (False, SEPARATE)):
        endpoint_pairs = []
        for path in paths:
            costs = set()
            for ledger in path.continuous:
                prices = tuple(product(*(term[-2:] for term in ledger.terms)))
                price_pairs = zip(prices, prices, strict=True) if shared else product(prices, repeat=2)
                for first, second in price_pairs:
                    candidate = ledger.opening + sum(term[0] * price for term, price in zip(
                        ledger.terms, first, strict=True))
                    control = ledger.opening + sum(term[1] * price for term, price in zip(
                        ledger.terms, second, strict=True))
                    costs.add((candidate, control))
            endpoint_pairs.append(costs)
        totals = [tuple(map(sum, zip(*choice, strict=True))) for choice in product(*endpoint_pairs)]
        values = [1 - Fraction(candidate, control) for candidate, control in totals]
        margin = min(GATE * control - candidate for candidate, control in totals)
        if [savings_bound(paths, maximize=flag, shared=shared, continuous=True) for flag in (True, False)] != [
                min(values), max(values)]:
            raise ValueError('The ratio solver differs from direct enumeration')
        candidate, control = total_cost(paths, GATE, maximize=True, shared=shared, continuous=True)
        if GATE * control - candidate != margin:
            raise ValueError('The gate margin differs from direct enumeration')
        counts[label] = len(totals)
    return counts


def read_terms(raw):
    rows = iter(raw.splitlines())
    header = next(rows, None)
    if header is None:
        raise ValueError('The path cost data is empty')
    data = json.loads(header)
    tasks = {}
    for line in rows:
        task, phase, comparison, terms = json.loads(line)
        if comparison not in (NATIVE, PAIRED):
            raise ValueError('Unknown path cost comparison')
        tasks.setdefault(task, {}).setdefault(phase, {}).setdefault(comparison, []).append(terms)
    return {**data, 'tasks': tasks}


def unpack(group):
    paths = []
    for count, opening, read_sets, witnesses in group:
        if type(count) is not int or count < 1 or type(opening) is not int or opening < 1:
            raise ValueError('Each path group requires a positive count and opening charge')
        if not read_sets or not witnesses or any(
                len(pair) != 2 or any(type(value) is not int or value <= 0 for value in pair) for pair in witnesses):
            raise ValueError('Each path group requires read sets and positive witnessed costs')
        for terms in read_sets:
            if any(type(value) is not int or value < 0 for term in terms for value in term):
                raise ValueError('Read counts and price bounds must be nonnegative integers')
            if any(low > high for _, _, low, high in terms):
                raise ValueError('A read has an inverted charge interval')
        paths.append(PathCosts(tuple(Ledger(opening, tuple(map(tuple, terms))) for terms in read_sets),
                               tuple(map(tuple, witnesses)), count))
    return paths


def measure(data, fixed_raw):
    if data['schema'] != 'sol-path-local-charge-terms-v1' or sha256(fixed_raw).hexdigest() != data['rowPairedTermsSha256']:
        raise ValueError('Use the versioned path and row-paired charge terms')
    fixed = fixed_bounds(json.loads(fixed_raw))
    tasks = data['tasks']
    if tasks.keys() != fixed['byTask'].keys() or any(
            group.keys() != fixed['byPhase'].keys() for group in tasks.values()):
        raise ValueError('Path and row-paired terms must cover the same tasks and seed sets')
    phases = tuple(next(iter(tasks.values())))

    def scope(groups, row_paired):
        paths = {arm: [path for group in groups for path in unpack(group.get(arm, ()))] for arm in (NATIVE, PAIRED)}
        count = sum(path.count for path in paths[NATIVE])
        if not count or sum(path.count for path in paths[PAIRED]) != count:
            raise ValueError('Both controls must account for the same paths')
        return {'paths': count, NATIVE: interval(paths[NATIVE]), PAIRED: interval(paths[PAIRED]),
                'tenPercentGateHeadroom': headroom(paths[NATIVE], row_paired)}

    return {
        'schema': 'sol-path-local-charge-headroom-v1', 'continuousReportSha256': data['continuousReportSha256'],
        'selectorRevision': data['selectorRevision'], 'newProviderRequests': 0,
        'solverEndpointChecks': verify_solver(), 'costGateMaximumRatio': str(GATE),
        'pooled': scope([group for task in tasks.values() for group in task.values()], fixed['pooled']),
        'byTask': {task: scope(list(groups.values()), fixed['byTask'][task]) for task, groups in tasks.items()},
        'bySeedSet': {phase: scope([task[phase] for task in tasks.values()], fixed['byPhase'][phase])
                      for phase in phases},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, nargs='?', default=DATA)
    args = parser.parse_args()
    print(json.dumps(measure(read_terms(args.data.read_bytes()), FIXED.read_bytes()), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
