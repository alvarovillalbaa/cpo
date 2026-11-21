"""Test independent qualification first when a validation-proven backup is absent."""

import argparse
from collections import Counter
from dataclasses import replace
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_math_validation_ties as math, recorded_training_backup as backup
from cpo._contract import digest


REFERENCE = 'docs/recorded-training-backup-results-v1.json'
REFERENCE_SHA256 = 'e5c74e67ab56d98935056ffb31ca8a85df10f222ff9f65cc20f98b20e50c74b0'
CANDIDATE = 'qualification-first-without-backup'
CONTROLS = {arm: f'{arm}-precheck' for arm in math.GEPA}
METHODS = (CANDIDATE, backup.PRECHECK, *CONTROLS.values())


def can_defer(incumbent, first, roster, validation, training, ledger, cap):
    if first == incumbent:
        return False
    missing = sum((prompt, row.id) not in ledger for row in training for prompt in (incumbent, first))
    return len(ledger) + missing <= cap and backup.strongest_backup(
        incumbent, first, roster, validation, ledger, partial=True) is None


def run_trial(cells, start, roster, cohorts, seed, cap):
    training_first = backup.select_with_training
    qualify = math.certify_paired_qualification
    deferred = None
    changes = Counter()

    def select(incumbent, first, roster, validation, training, observe, ledger, *, cap, seed, mode, audit):
        nonlocal deferred
        if can_defer(incumbent, first, roster, validation, training, ledger, cap):
            deferred = partial(training_first, incumbent, first, (), validation, training, observe, ledger,
                               cap=cap, seed=seed, mode=mode, audit=audit)
            changes['deferredTraining'] += 1
            return first
        return training_first(incumbent, first, roster, validation, training, observe, ledger,
                              cap=cap, seed=seed, mode=mode, audit=audit)

    def confirm(incumbent, challenger, rows, evaluate, *, seed):
        decision = qualify(incumbent, challenger, rows, evaluate, seed=seed)
        if deferred is None:
            return decision
        if decision.status != 'promoted':
            changes['trainingSkippedAfterQualification'] += 1
        elif deferred() != challenger:
            changes['trainingVetoAfterQualification'] += 1
            decision = replace(decision, status='rejected', prompt=incumbent)
        return decision

    with (patch.object(backup, 'select_with_training', select),
          patch.object(math, 'certify_paired_qualification', confirm)):
        total, trace, values = backup.run_trial(cells, start, roster, cohorts, seed, backup.PRECHECK, cap)
    return {**total, **changes}, trace, values


def prepare():
    prior, data, _ = backup.prepare()
    raw = (backup.ROOT / REFERENCE).read_bytes()
    published = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or published['planSha256'] != digest(prior):
        raise ValueError('Use the exact published training-backup replay')
    plan = {**{name: prior[name] for name in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                             'gepaVersion', 'bootstrapSeed', 'bootstrapDraws',
                                             'minimumLookupSavingPercent')},
            'protocol': 'recorded-training-proof-order-v1', 'parentPlanSha256': digest(prior),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS,
            'rule': 'Run the matched incumbent qualification precheck and original validation search. When the '
                    'full training reserve fits and no paid validation backup is eligible, perform the same '
                    'independent qualification before training. Keep training first in all other cases. Verify '
                    'that every deployment matches the original certified backup policy.'}
    return plan, data, published['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals = {arm: Counter() for arm in METHODS}
    traces = {arm: [] for arm in METHODS}
    vectors = {arm: [0] * size for arm in METHODS}
    costs = Counter()
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            arguments = (cells, start, roster, cohorts, seed)
            limit = plan['searchCap']
            original = backup.run_trial(*arguments, backup.PRECHECK, limit)
            candidate = run_trial(*arguments, limit)
            if original[1][3] != candidate[1][3] or original[2] != candidate[2]:
                raise ValueError('Reordering the two proofs changed the deployed prompt or held-out grades')
            saved = original[0]['paidLookups'] - candidate[0]['paidLookups']
            costs.update(cheaper=int(saved > 0), dearer=int(saved < 0), equal=int(saved == 0),
                         grossLookupsSaved=max(0, saved), grossExtraLookups=max(0, -saved))
            outcomes = {CANDIDATE: candidate, backup.PRECHECK: original}
            outcomes.update({arm: backup.run_trial(*arguments, arm, limit) for arm in CONTROLS.values()})
            for arm, (point, trace, grades) in outcomes.items():
                totals[arm].update(point)
                traces[arm].append(trace)
                for case, passed in zip(cohorts[-1], grades, strict=True):
                    vectors[arm][case] += passed
    points = {arm: {**count, 'traceSha256': digest(traces[arm])} for arm, count in totals.items()}
    if any(points[arm] != reference['totals'][arm] for arm in (backup.PRECHECK, *CONTROLS.values())):
        raise ValueError('The original CPO or GEPA comparison does not reproduce its published trace')
    matched_vectors = {**vectors, **{arm: vectors[actual] for arm, actual in CONTROLS.items()}}
    matched_totals = {**totals, **{arm: totals[actual] for arm, actual in CONTROLS.items()}}
    ranges = math.paired_ranges(matched_vectors, CANDIDATE, math.GEPA, plan)
    return {'totals': points, 'deploymentChecks': len(traces[CANDIDATE]), 'costChanges': costs,
            'comparison': math.comparison(CANDIDATE, matched_totals, ranges, plan)}


def replay(plan, data, references):
    result = {}
    for name, settings in plan['datasets'].items():
        cells = math.load_cells(name, data[name]['record'])
        result[name] = {f'{group}/{width}': measure(cells, settings, group, width, plan,
                                                   references[name][f'{group}/{width}'])
                        for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': result}


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
