"""Compare two rules for using training evidence after independent qualification."""

import argparse
from collections import Counter, deque
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_calibrated_training_route as prior
from cpo._contract import digest


parent, transfer, math, core = prior.parent, prior.transfer, prior.math, prior.core
REFERENCE = 'docs/recorded-calibrated-training-route-results-v1.json'
REFERENCE_SHA256 = '1bbe3cd66272b46c638b7dfa698361e0257c369b545086394f9a63c1c21d193d'
NONLOSS = 'training-nonloss'
BALANCED = 'positive-mean-of-panel-gains'
ARMS = (NONLOSS, BALANCED)


def settle_balanced(prompts, panels, observe, paid, rates, prices):
    """Prove positive mean gain rate using the requested rows and paid grades."""
    qualification, training = panels
    weights = len(training), len(qualification)
    if not all(weights):
        raise ValueError('Both proof panels must contain cases')
    needed = 1 + sum(weight * len(rows) for weight, rows in zip(weights, panels, strict=True))
    possible = 0
    pending = {}
    for panel, (rows, ledger, weight) in enumerate(zip(panels, paid, weights, strict=True)):
        for side, prompt in enumerate(prompts):
            unread = pending[panel, side] = deque()
            for row in rows:
                key = prompt, row.id
                if key in ledger:
                    needed -= weight * (ledger[key] == bool(side))
                else:
                    unread.append(row)
                    possible += weight

    def priority(slot):
        panel, side = slot
        chance = rates[side] if needed <= possible - needed + 1 else 4 - rates[side]
        return Fraction(weights[panel] * chance, prices[side])

    while 0 < needed <= possible:
        panel, side = max((slot for slot, rows in pending.items() if rows), key=priority)
        row = pending[panel, side].popleft()
        passed = observe[panel](prompts[side], row)
        if type(passed) is not bool:
            raise ValueError('The joint proof requires exact boolean grades')
        weight = weights[panel]
        needed -= weight * (passed == bool(side))
        possible -= weight
    return needed <= 0


def run_trial(cells, start, roster, cohorts, seed, cap, arm):
    original_proof, original_training = prior.adapter.qualify_with_prefix, parent.settle
    qualification = None
    additional = 0

    def qualify(incumbent, challenger, rows, read, prefix, counts, proof_seed, mode):
        nonlocal qualification
        decision = original_proof(incumbent, challenger, rows, read, prefix, counts, proof_seed, mode)
        qualification = rows, read, decision
        return decision

    def corroborate(prompts, training, evaluate, ledger, rates, prices, *, minimum_gain):
        if arm == NONLOSS:
            return original_training(prompts, training, evaluate, ledger, rates, prices, minimum_gain=0)
        rows, read, proof = qualification
        if proof.status != 'promoted' or proof.lower_gain < 1:
            raise ValueError('Joint corroboration requires a strict independent gain first')
        paid_proof = {(entry.prompt, entry.row_id): entry.passed for entry in proof.observations}
        paid_training = {(prompt, row.id): ledger[prompt, row.id].passed for prompt in prompts for row in training
                         if (prompt, row.id) in ledger}

        def extend(prompt, row):
            nonlocal additional
            additional += 1
            return read(prompt, row, 0)

        return settle_balanced(prompts, (rows, training), (extend, lambda prompt, row: evaluate(prompt, row).passed),
                               (paid_proof, paid_training), rates, prices)

    with (patch.object(prior.adapter, 'qualify_with_prefix', qualify), patch.object(parent, 'settle', corroborate)):
        point, trace, grades, bucket = prior.run_trial(cells, start, roster, cohorts, seed, cap, prior.STRATA)
    return {**point, 'extraQualificationLookups': additional}, trace, grades, bucket


def prepare():
    inherited, data, controls, baseline, _, _ = prior.prepare()
    proof_reference = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-joint-training-qualification-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'methods': (*ARMS, prior.NEVER, prior.ALWAYS, parent.ORDERED),
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Keep the seeded strict nominee and independent gain of at least one pass. Compare '
                     'nonnegative training gain with positive mean of the qualification and training gain '
                     'rates. Weight the gains by the opposite panel sizes. Credit the original qualification '
                     'prefix. Schedule only unread pairs by expected weighted evidence per charge, with '
                     'rates and prices frozen from paid validation. Keep both role caps and compare to the '
                     'original matched historical cost and lookup frontiers.'}
    return plan, data, controls, baseline, proof_reference['results']


def measure(plan, cells, settings, group, width, controls, baseline, reference, arm):
    changes, never = Counter(), Counter()

    def trial(*args):
        args = args[:-1]
        point, trace, grades, bucket = run_trial(*args, arm)
        old, old_trace, old_grades, original_bucket = prior.run_trial(*args, ())
        never.update(old)
        extra = point['extraQualificationLookups']
        if (bucket != original_bucket or trace[:3] != old_trace[:3]
                or point['qualificationLookups'] != old['qualificationLookups'] + extra
                or point['qualificationLookups'] > 2 * len(args[3][2])
                or point['searchLookups'] != old['searchLookups'] + point.get('trainingLookups', 0)
                or (bucket is None and (trace != old_trace or grades != old_grades))):
            raise ValueError('The additional proof must preserve the original nomination, gate and limits')
        delta = sum(grades) - sum(old_grades)
        changes.update(affectedTrials=int(bucket is not None), changedDeployments=int(trace[3] != old_trace[3]),
                       heldoutPassDelta=delta, grossPassGain=max(0, delta), grossPassLoss=max(0, -delta),
                       additionalLookups=point['paidLookups'] - old['paidLookups'])
        if transfer.HISTORICAL in point:
            changes['addedHistoricalCostNanodollars'] += point[transfer.HISTORICAL] - old[transfer.HISTORICAL]
        return point, trace, grades

    original = core.trial

    def existing(*args):
        return parent.run_trial(*args[:-1]) if args[-1] == parent.ORDERED else original(*args)

    anchors = {**controls, 'totals': {**controls['totals'], parent.ORDERED: baseline['anchors'][parent.ORDERED]}}
    with (patch.object(transfer, 'PRIMARY', arm), patch.object(transfer, 'METHODS', (arm, parent.ORDERED, core.FIRST)),
          patch.object(core, 'trial', existing), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    if (never != reference['totals'][prior.NEVER]
            or any(point != baseline['totals'][label] for label, point in result['totals'].items() if label != arm)
            or any(value[parent.ORDERED] != baseline['comparisons'][key][parent.ORDERED]
                   for key, value in result['comparisons'].items())):
        raise ValueError('Earlier training and GEPA receipts must reproduce exactly')
    return {'totals': result['anchors'][arm], 'pairedChangesVsNoTraining': changes,
            'comparisons': {key: value[arm] for key, value in result['comparisons'].items()}}


def replay(plan, data, controls, baseline, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                original = reference[dataset][name]['totals']
                results[dataset][name] = {'fixedThresholds': {arm: original[arm] for arm in (prior.NEVER, prior.ALWAYS)},
                                          **{arm: measure(plan, cells, settings, group, width, controls[dataset][name],
                                                          baseline[dataset][name], reference[dataset][name], arm)
                                             for arm in ARMS}}
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
