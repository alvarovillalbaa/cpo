"""Compare validation allocation policies on the same recorded prompt pools."""

import argparse
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from importlib.metadata import version
import json
from math import comb, factorial
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import pool
from benchmarks import recorded_math_validation_ties as math
from benchmarks import recorded_training_backup as backup
from benchmarks import recorded_validation_stability as prior
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SHA256 = 'e28e02dd61f2a53ca927c5a389774647bad110b8d4b8c5074667cd96e99d0fbb'
CAPS = (36, 52)
WIDTH = 8
GEPA = tuple(prior.QUALIFICATION_PRECHECK.values())
CONTROLS = ('retain-start', 'strict-precheck', 'full-score-history', 'successive-halving', *GEPA)
METHODS = (*CONTROLS, 'posterior-allocation')


@lru_cache(maxsize=4096)
def predictive_chance(passed, failed, unread, target):
    """Beta-binomial probability that a partially read prompt can reach target."""
    needed = max(0, target - passed)
    if needed > unread:
        return Fraction(0)
    a, b = passed + 1, failed + 1
    denominator = factorial(a + b + unread - 1) // factorial(a + b - 1)
    favourable = 0
    for gains in range(needed, unread + 1):
        successes = factorial(a + gains - 1) // factorial(a - 1)
        failures = factorial(b + unread - gains - 1) // factorial(b - 1)
        favourable += comb(unread, gains) * successes * failures
    return Fraction(favourable, denominator)


def allocate(incumbent, candidates, rows, observe, journal, *, limit):
    """Choose replies using score predictions and nominate only exact improvements."""
    rows, candidates = tuple(rows), tuple(candidates)
    if limit < len(rows) or not rows:
        raise ValueError('The search budget must cover the complete incumbent panel')
    baseline = {row.id: observe(incumbent, row).passed for row in rows}
    protected = {row.id for row in rows if row.critical and baseline[row.id]}
    pass_counts, seen_counts = Counter(baseline), Counter(dict.fromkeys(baseline, 1))
    order = {prompt: index for index, prompt in enumerate((incumbent, *candidates))}
    pending = {prompt: list(rows) for prompt in candidates}
    scores = dict.fromkeys(candidates, 0)
    leader, best = incumbent, sum(baseline.values())
    while pending:
        options = {}
        remaining = limit - len(journal)
        for prompt, unread in pending.items():
            target = best + int(order[prompt] > order[leader])
            passed = scores[prompt]
            if not unread or len(unread) > remaining or passed + len(unread) < target:
                continue
            probability = predictive_chance(passed, len(rows) - len(unread) - passed, len(unread), target)
            options[prompt] = probability, -len(unread), -order[prompt]
        if not options:
            break
        candidate = max(options, key=options.__getitem__)
        unread = pending[candidate]
        row = min(unread, key=lambda row: (
            row.id not in protected, Fraction(pass_counts[row.id] + 1, seen_counts[row.id] + 2)))
        unread.remove(row)
        passed = observe(candidate, row).passed
        pass_counts[row.id] += passed
        seen_counts[row.id] += 1
        scores[candidate] += passed
        if not passed and row.id in protected:
            del pending[candidate]
        elif not unread and (scores[candidate], -order[candidate]) > (best, -order[leader]):
            leader, best = candidate, scores[candidate]
    return leader


def full_score_history(incumbent, candidates, rows, observe, journal, *, limit):
    leader = incumbent
    baseline = {row.id: observe(incumbent, row).passed for row in rows}
    best = sum(baseline.values())
    for prompt in candidates:
        if best == len(rows) or len(journal) + len(rows) > limit:
            break
        values = {row.id: observe(prompt, row).passed for row in rows}
        passes = sum(values.values())
        if passes > best and all(not row.critical or not baseline[row.id] or values[row.id] for row in rows):
            leader, best = prompt, passes
    return leader


def run_trial(cells, start, roster, cohorts, seed, method, cap):
    if method in ('retain-start', 'strict-precheck', *GEPA):
        return prior.run_trial(cells, start, roster, cohorts, seed, method, cap)

    def select(incumbent, candidates, rows, observe, journal, *, method, cap):
        if policy == 'successive-halving':
            choice = pool.successive_halving((incumbent, *candidates), rows,
                                              lambda prompt, row: observe(prompt, row).passed, cap)
        else:
            choose = allocate if policy == 'posterior-allocation' else full_score_history
            choice = choose(incumbent, candidates, rows, observe, journal, limit=cap)
        return choice, False

    policy = method
    with (patch.object(math, 'select', select), patch.dict(backup.PRECHECKED, {'strict-precheck': 'strict'})):
        return backup.run_prechecked(cells, start, roster, cohorts, seed, 'strict-precheck', cap)


def prepare():
    parent, data, _ = prior.prepare()
    raw = (ROOT / 'docs/recorded-validation-stability-results-v1.json').read_bytes()
    report = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or report['planSha256'] != digest(parent):
        raise ValueError('The archived qualification controls differ from the published reference')
    paths = ('benchmarks/recorded_score_allocation.py', 'benchmarks/pool.py',
             'benchmarks/gepa_paid_cap_transfer.py', *parent['sourceSha256'])
    plan = {**{k: parent[k] for k in ('datasets', 'gepaVersion', 'bootstrapSeed', 'bootstrapDraws',
                                     'minimumLookupSavingPercent')},
            'protocol': 'cpo-recorded-score-allocation-v1', 'priorPlanSha256': digest(parent),
            'sourceReportSha256': REFERENCE_SHA256, 'methods': METHODS, 'searchCaps': CAPS, 'challengers': WIDTH,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'scope': ('Use rotated starts and the original seeded rosters. Allocate validation replies from a '
                      'shared fixed prompt pool under two paid caps. All arms use the incumbent precheck and '
                      'independent qualification. Report recorded ARC costs and AIME lookup counts.')}
    return plan, data


def measure(cells, settings, cap, plan):
    size = len(next(iter(cells.values())))
    amounts, logs = ({m: factory() for m in METHODS} for factory in (Counter, list))
    outcomes = {m: [0] * size for m in METHODS}
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in tuple(cells)[1:]:
            others = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(others, len(others))[:plan['challengers']]
            for method in METHODS:
                point, trace, outcomes_for_trial = run_trial(cells, start, roster, cohorts, seed, method, cap)
                if point['searchLookups'] > cap:
                    raise ValueError('An arm went over the search allowance')
                amounts[method].update(point)
                logs[method].append(trace)
                for case, passed in zip(cohorts[-1], outcomes_for_trial, strict=True):
                    outcomes[method][case] += passed
    totals = {m: {**values, 'traceSha256': digest(logs[m])} for m, values in amounts.items()}
    if any(sum(vector) != totals[method]['holdoutPasses'] for method, vector in outcomes.items()):
        raise ValueError('Holdout vectors do not reproduce the exact trial totals')
    cpo, candidate = 'strict-precheck', 'posterior-allocation'
    matched = {**amounts, **{control: amounts[arm] for control, arm in prior.QUALIFICATION_PRECHECK.items()}}
    vectors = {**outcomes, **{control: outcomes[arm] for control, arm in prior.QUALIFICATION_PRECHECK.items()}}
    controls = (*math.GEPA, 'full-score-history', 'successive-halving', cpo, 'retain-start')
    ranges = math.paired_ranges(vectors, candidate, controls, plan)
    return {'totals': totals, 'trialsPerMethod': len(logs[candidate]),
            'posteriorVsGepa': math.comparison(candidate, matched, ranges, plan)}


def replay(plan, data):
    results = {}
    for domain, settings in plan['datasets'].items():
        cells = math.load_cells(domain, data[domain]['record'])
        results[domain] = {str(cap): measure(cells, settings, cap, plan) for cap in plan['searchCaps']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, data)
    with args.out.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
