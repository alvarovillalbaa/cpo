"""Raise the exact validation target sooner on fixed archived challenger rosters."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_paid_qualification_order as parent
from cpo._contract import digest


math, prior = parent.math, parent.prior
REFERENCE = 'docs/recorded-paid-qualification-order-results-v1.json'
REFERENCE_SHA256 = 'a7e0d401c77b4951bc381922b2ae48218f459a856d4d095d7c369fbcac76d677'
RECENCY = 'recent-first'
PROBE = 'one-shared-missed-case-probe'
POLICIES = (RECENCY, PROBE)
ARMS = (*parent.ARMS, *POLICIES)


def select(incumbent, candidates, rows, observe, *, cap, policy, chronology):
    """Change dispatch order while preserving exact rank and incumbent critical replies."""
    if (len(rows) * (len(candidates) + 1) > cap or not rows or len({row.id for row in rows}) != len(rows)
            or len({incumbent, *candidates}) != len(candidates) + 1):
        raise ValueError('The exact reordered race needs distinct rows, candidates, and a fully funded panel')
    precedence = {prompt: index for index, prompt in enumerate((incumbent, *candidates))}
    grades, successes, seen = {}, Counter(), Counter()
    scouting = 0

    def read(prompt, row):
        key = prompt, row.id
        if key not in grades:
            answer = observe(prompt, row).passed
            if type(answer) is not bool:
                raise ValueError('Validation requires exact boolean grades')
            grades[key] = answer
            seen[row.id] += 1
            successes[row.id] += answer
        return grades[key]

    passed = {row.id for row in rows if read(incumbent, row)}
    protected = {row.id for row in rows if row.critical and row.id in passed}
    leader, score = incumbent, len(passed)
    if score == len(rows):
        return leader, scouting
    if policy == RECENCY:
        ordered = sorted(candidates, key=chronology.__getitem__, reverse=True)
    elif policy == PROBE:
        probe = next(row for row in rows if row.id not in passed)
        signals = {name: read(name, probe) for name in candidates}
        ordered = sorted(candidates, key=signals.__getitem__, reverse=True)
        scouting = len(signals)
    else:
        raise ValueError('Use a declared validation order')

    for name in ordered:
        target = score + (precedence[name] > precedence[leader])
        known = sum(grades.get((name, row.id), False) for row in rows)
        remaining = [row for row in rows if (name, row.id) not in grades]
        if known + len(remaining) < target or any(grades.get((name, case)) is False for case in protected):
            continue
        ranked = sorted(remaining, key=lambda row: (
            row.id not in protected, Fraction(successes[row.id] + 1, seen[row.id] + 2)))
        for index, row in enumerate(ranked, 1):
            correct = read(name, row)
            known += correct
            if (not correct and row.id in protected) or known + len(ranked) - index < target:
                break
        else:
            leader, score = name, known
    return leader, scouting


def run(cells, start, roster, cohorts, seed, cap, arm, chronology):
    original = math.select
    audit = {}
    winner, backup = start, None

    def choose(incumbent, candidates, rows, observe, ledger, *, method, cap):
        nonlocal winner, backup
        if arm in POLICIES:
            winner, scouts = select(incumbent, candidates, rows, observe, cap=cap, policy=arm, chronology=chronology)
            audit.update(sharedProbeLookups=scouts, validationLookups=len(ledger))
            tied = False
        else:
            winner, tied = original(incumbent, candidates, rows, observe, ledger, method=method, cap=cap)
        if winner != incumbent:
            backup = parent.backup.strongest_backup(incumbent, winner, candidates, rows, ledger, partial=True)
        return winner, tied

    with patch.object(math, 'select', choose):
        mode = prior.CANDIDATE if arm in POLICIES else arm
        point, trace, outcomes = parent.run_trial(cells, start, roster, cohorts, seed, cap, mode, parent.EXPECTED)
    return {**point, **audit}, trace, outcomes, winner, backup


def prepare():
    inherited, data, _ = parent.prepare()
    raw = (parent.backup.ROOT / REFERENCE).read_bytes()
    published = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or published['planSha256'] != digest(inherited):
        raise ValueError('Use the exact published expected-cost qualification comparison')
    plan = {**{name: inherited[name] for name in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                                  'gepaVersion', 'bootstrapSeed', 'bootstrapDraws',
                                                  'minimumLookupSavingPercent')},
            'protocol': 'recorded-validation-race-order-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'arms': ARMS,
            'scope': 'Retain seed rosters, exact validation score, seed rank for ties, and protected critical passes. '
                     'Race newest recorded discovery first or rank by one shared check on an incumbent miss. '
                     'Use the same training and independent qualification gates and matched GEPA controls. '
                     'Record changes in paid backup availability and final deployment.'}
    return plan, data, published['results']


def measure(cells, chronology, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals, traces = {arm: Counter() for arm in ARMS}, {arm: [] for arm in ARMS}
    vectors, changes = {arm: [0] * size for arm in ARMS}, {arm: Counter() for arm in POLICIES}
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            args = (cells, start, roster, cohorts, seed, plan['searchCap'])
            observed = {arm: run(*args, arm, chronology) for arm in ARMS}
            baseline, prior_trace, _, prior_winner, prior_backup = observed[prior.CANDIDATE]
            for arm in POLICIES:
                point, trace, _, winner, backup = observed[arm]
                if winner != prior_winner:
                    raise ValueError('Both funded races must preserve the exact validation winner')
                delta = point['holdoutPasses'] - baseline['holdoutPasses']
                changes[arm].update(awayFromBaseline=int(trace[3] != prior_trace[3]), improved=int(delta > 0),
                                    regressed=int(delta < 0), grossGain=max(0, delta), grossLoss=max(0, -delta),
                                    backupGained=int(prior_backup is None and backup is not None),
                                    backupLost=int(prior_backup is not None and backup is None),
                                    backupChanged=int(prior_backup != backup))
            for arm, (point, trace, values, *_) in observed.items():
                totals[arm].update(point)
                traces[arm].append(trace)
                for case, grade in zip(cohorts[-1], values, strict=True):
                    vectors[arm][case] += grade
    points = {arm: {**point, 'traceSha256': digest(traces[arm])} for arm, point in totals.items()}
    if any(points[arm] != reference['totals'][parent.EXPECTED][arm] for arm in parent.ARMS):
        raise ValueError('The archived CPO and GEPA control traces must reproduce')
    matched = {**totals, **{name: totals[arm] for name, arm in prior.CONTROLS.items()}}
    grades = {**vectors, **{name: vectors[arm] for name, arm in prior.CONTROLS.items()}}
    return {'totals': points, 'trialCount': len(traces[RECENCY]), 'deploymentChanges': changes,
            'comparison': {arm: math.comparison(arm, matched, math.paired_ranges(grades, arm, math.GEPA, plan), plan)
                           for arm in POLICIES}}


def replay(plan, data, reference):
    results = {}
    for name, settings in plan['datasets'].items():
        record = data[name]['record']
        cells = math.load_cells(name, record)
        clock = 'iteration' if name == 'aime' else 'discoveryCalls'
        chronology = {str(candidate['id']): candidate[clock] for candidate in record['candidates']}
        results[name] = {f'{group}/{width}': measure(cells, chronology, settings, group, width, plan,
                                                    reference[name][f'{group}/{width}'])
                         for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, data, reference)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
