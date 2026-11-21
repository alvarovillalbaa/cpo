"""Rank two paid nominees by the smaller validation and training gain."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_expected_training_order as parent
from cpo._contract import digest


transfer, math, core = parent.math_transfer, parent.math, parent.core
REFERENCE = 'docs/recorded-expected-training-order-results-v1.json'
REFERENCE_SHA256 = '49a761d5acc0b549855e9a51b8ee47243ab4e9ec2767a7875e65b0adc3e91329'
ARM = 'corroborated-nomination'
METHODS = (ARM, parent.ORDERED, core.FIRST)


def nominate(incumbent, offers, prove):
    """Prove only the gain thresholds that can change the first eligible choice."""
    (first, first_gain), (backup, backup_gain) = offers
    winner, best = incumbent, 0
    # A training gain above the backup's validation bound cannot break any tie.
    for prompt, limit in ((first, min(first_gain, backup_gain)), (backup, backup_gain)):
        for target in range(best + 1, limit + 1):
            if not prove(prompt, target):
                break
            winner, best = prompt, target
    return winner


def retrospective_ceiling(cells, incumbent, offers, cohorts):
    """Score the best admissible deployment with hindsight and free proofs."""
    train, _, qualification, heldout = cohorts
    training = train[:len(train) // 2]

    def score(prompt, rows):
        return sum(cells[prompt][case][0] for case in rows)

    eligible = [incumbent, *(prompt for prompt in offers if all(
        score(prompt, rows) > score(incumbent, rows) for rows in (training, qualification)))]
    return max(score(prompt, heldout) for prompt in eligible)


def run_trial(cells, start, roster, cohorts, seed, cap):
    backup = core.backup
    original = backup.select_with_training
    changes = Counter()
    contenders = ()

    def select(incumbent, first, roster, validation, training, observe, ledger, *, cap, seed, mode, audit):
        nonlocal contenders
        rival = (backup.strongest_backup(incumbent, first, roster, validation, ledger, partial=True)
                 if first != incumbent and roster else None)
        if rival is None or len(ledger) + sum((prompt, row.id) not in ledger for row in training
                                              for prompt in (incumbent, first, rival)) > cap:
            return original(incumbent, first, roster, validation, training, observe, ledger,
                            cap=cap, seed=seed, mode=mode, audit=audit)

        contenders = first, rival
        base = sum(ledger[incumbent, row.id].passed for row in validation)
        offers = [(prompt, sum(ledger[prompt, row.id].passed for row in validation
                               if (prompt, row.id) in ledger) - base) for prompt in contenders]
        if not all(gain > 0 for _, gain in offers):
            raise ValueError('Both contenders must have proven strict validation gains')
        estimates = {prompt: parent.estimate((incumbent, prompt), validation, ledger, cells) for prompt, _ in offers}
        tried = set()

        def prove(prompt, target):
            tried.add(prompt)
            rates, prices = estimates[prompt]
            return parent.settle((incumbent, prompt), training, observe, ledger, rates, prices, minimum_gain=target)

        before = len(ledger)
        winner = nominate(incumbent, offers, prove)
        changes.update(paidAlternateTrials=1, comparedAlternate=int(rival in tried),
                       alternateNominations=int(winner == rival), neitherCorroborated=int(winner == incumbent))
        audit.update(trainingChecks=len(tried), trainingLookups=len(ledger) - before)
        return winner

    with patch.object(backup, 'select_with_training', select):
        point, trace, grades = parent.run_trial(cells, start, roster, cohorts, seed, cap)
    if contenders:
        ceiling = retrospective_ceiling(cells, start, contenders, cohorts)
        if ceiling < sum(grades):
            raise ValueError('Retrospective proof eligibility must include the deployed prompt')
        changes['retrospectiveCeilingPasses'] = ceiling
    if point['searchLookups'] > cap or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']:
        raise ValueError('Every paid comparison must fit within the original allowance')
    return {**point, **changes}, trace, grades


def prepare():
    inherited, data, controls, _ = parent.prepare()
    archive = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-corroborated-nomination-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'methods': METHODS,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'After seeded validation, compare its winner and the existing paid backup by the '
                     'smaller of the proven validation gain and exact training gain. Break ties in original '
                     'nominee order. Buy only training proofs that can change this ranking. Keep all existing '
                     'strict gates and qualify at most one challenger. Fall back to the original policy '
                     'without a certified backup or a funded full training reserve. After selection, compute '
                     'an optimistic reranking ceiling with free training and qualification for both paid '
                     'offers, and choose using the archived holdout. This diagnostic changes no decision.'}
    return plan, data, controls, archive['results']


def measure(plan, cells, settings, group, width, controls, reference):
    changes = Counter()

    def trial(*args):
        args = args[:-1]
        baseline, old, original_grades = parent.run_trial(*args)
        point, trace, grades = run_trial(*args)
        delta = sum(grades) - sum(original_grades)
        if not point.get('paidAlternateTrials') and (trace != old or grades != original_grades or point != baseline):
            raise ValueError('Trials without an affordable paid alternate must follow the original path')
        changes.update(trials=1, changedNominations=int(trace[2] != old[2]),
                       changedDeployments=int(trace[3] != old[3]), heldoutPassDelta=delta,
                       grossPassGains=max(delta, 0), grossPassLosses=max(-delta, 0),
                       extraLookups=point['paidLookups'] - baseline['paidLookups'])
        if transfer.HISTORICAL in baseline:
            changes['extraHistoricalCostNanodollars'] += point[transfer.HISTORICAL] - baseline[transfer.HISTORICAL]
        if 'retrospectiveCeilingPasses' in point:
            headroom = point['retrospectiveCeilingPasses'] - sum(original_grades)
            if headroom < 0:
                raise ValueError('The ceiling must also include the original deployment')
            changes.update(hindsightGainOverBaseline=headroom, hindsightImprovedTrials=int(headroom > 0))
        return point, trace, grades

    original = core.trial

    def existing(*args):
        return parent.run_trial(*args[:-1]) if args[-1] == parent.ORDERED else original(*args)

    anchors = {**controls, 'totals': {**controls['totals'], parent.ORDERED: reference['anchors'][parent.ORDERED]}}
    with (patch.object(transfer, 'PRIMARY', ARM), patch.object(transfer, 'METHODS', METHODS),
          patch.object(core, 'trial', existing), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    if (any(point != reference['totals'][label] for label, point in result['totals'].items() if label != ARM)
            or any(value[parent.ORDERED] != reference['comparisons'][key][parent.ORDERED]
                   for key, value in result['comparisons'].items())
            or any(changes[delta] != result['totals'][ARM][metric] - reference['totals'][parent.ORDERED][metric]
                   for delta, metric in (('heldoutPassDelta', 'holdoutPasses'), ('extraLookups', 'paidLookups')))):
        raise ValueError('The archived anchors, cost frontier, and paired totals must reconcile')
    return {'totals': result['anchors'][ARM], 'pairedChanges': changes,
            'comparisons': {key: value[ARM] for key, value in result['comparisons'].items()}}


def replay(plan, data, controls, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = measure(plan, cells, settings, group, width,
                                                 controls[dataset][name], reference[dataset][name])
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
