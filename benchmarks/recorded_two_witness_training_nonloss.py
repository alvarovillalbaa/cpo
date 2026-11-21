"""Compare strict training improvement with training nonloss on archived MMLU."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_two_witness_mmlu_transfer as mmlu
from cpo._contract import digest


model_transfer = mmlu.model_transfer
transfer, cost = mmlu.transfer, mmlu.cost
training = model_transfer.shortlist.adapter.backup.prior
corroborate = training.corroborate
STRICT = model_transfer.screen.PAIRED
NONLOSS = 'two-witness-training-nonloss'
METHODS = (STRICT, NONLOSS)
ARCHIVES = {'posterior-model-transfer-v1.json': '6cefcc4ccc4d2dd197dcdff2294b178e14ccdd5de6819e03b66edf821b09efec'}
REFERENCE = 'docs/recorded-two-witness-mmlu-transfer-results-v1.json'
REFERENCE_SHA256 = '5c043b5fc8458cf924bf868e03fc410f2c82e437294d6e0024279c0ddc0487ff'


def prepare():
    anchor, development = mmlu.prepare()
    reference = cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, anchor)
    _, original, _, _ = cost.prior.prepare()
    _, previous = mmlu.parity.prepare()
    known = original + development + [panel for rows in previous.values() for panel, _ in rows]
    with patch.object(transfer, 'ARCHIVES', ARCHIVES):
        confirmation, excluded = mmlu.enroll(transfer.load_panels(), known)
    cohorts = {'previous-mmlu': development, 'disjoint-mmlu': confirmation}
    plan = {**{key: anchor[key] for key in ('gepaVersion', 'bootstrapSeed', 'bootstrapDraws', 'searchCap',
                                            'minimumSearchCap', 'seeds', 'challengers', 'caseCounts')},
            'protocol': 'recorded-two-witness-training-nonloss-v1', 'parentPlanSha256': digest(anchor),
            'parentReceiptSha256': REFERENCE_SHA256, 'archivesSha256': ARCHIVES,
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'arms': METHODS, 'minimumTrainingGain': {STRICT: 1, NONLOSS: 0},
            'enrolledPanels': {name: [panel[:3] for panel in panels] for name, panels in cohorts.items()},
            'excludedPreviouslyExaminedTasks': excluded,
            'scope': 'Change only the first-half training gain threshold from one to zero. Preserve search, '
                     'validation gain, training reserve, qualification gain, and the GEPA cost frontier. '
                     'Test the same change on the previous cohort and a held-out task and model cohort.'}
    return plan, cohorts, reference['results']


def training_nonloss(incumbent, challenger, rows, observe, *, minimum_gain, remaining, seed):
    if minimum_gain != 1:
        raise ValueError('Expected the original strict training threshold')
    return corroborate(incumbent, challenger, rows, observe, minimum_gain=0, remaining=remaining, seed=seed)


def run_trial(*args):
    guard = training_nonloss if args[-1] == NONLOSS else corroborate
    with (patch.object(model_transfer.shortlist, 'shortlist', mmlu.parity.use_public),
          patch.object(training, 'corroborate', guard)):
        return model_transfer.shortlist.trial(*args)


def full_cap(subject, matrix, plan):
    old_trial = transfer.study.trial

    def trial(*args):
        return run_trial(*args) if args[-1] in METHODS else old_trial(*args)

    with (patch.object(transfer, 'METHODS', (*METHODS, *cost.MODES, cost.frontier.RETAIN)),
          patch.object(transfer.study, 'trial', trial)):
        return transfer.measure_panel(matrix, subject, plan)


def paired_change(plan, panels, results):
    counts, differences = Counter(), {}
    for _, subject, _, matrix in panels:
        cells = {str(index): tuple((int(passed), None, False) for passed in vector)
                 for index, vector in enumerate(matrix)}
        for seed in plan['seeds']:
            start, roster, cohorts = transfer.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
            args = (cells, start, roster, cohorts, seed, plan['searchCap'])
            strict, old_trace, old_grades = run_trial(*args, STRICT)
            relaxed, new_trace, new_grades = run_trial(*args, NONLOSS)
            if (old_trace[:3] != new_trace[:3] or strict['qualificationLookups'] != relaxed['qualificationLookups']
                    or strict['searchLookups'] - strict.get('trainingLookups', 0)
                    != relaxed['searchLookups'] - relaxed.get('trainingLookups', 0)):
                raise ValueError('A training threshold change must preserve the nomination and other paid stages')
            if old_trace[3] != new_trace[3]:
                if old_trace[3] != start or new_trace[3] != new_trace[2]:
                    raise ValueError('Nonloss may only restore the qualified nominee after a strict training veto')
                halfway = cohorts[0][:len(cohorts[0]) // 2]
                if sum(cells[new_trace[3]][case][0] - cells[start][case][0] for case in halfway) != 0:
                    raise ValueError('A restored deployment must tie on training')
                counts['restoredTrainingTies'] += 1
            gain = relaxed['holdoutPasses'] - strict['holdoutPasses']
            counts.update(trials=1, grossPassGain=max(0, gain), grossPassLoss=max(0, -gain),
                          lookupDelta=relaxed['paidLookups'] - strict['paidLookups'])
            current = differences.get(subject, [0] * len(old_grades))
            differences[subject] = [delta + new - old for delta, new, old in
                                    zip(current, new_grades, old_grades, strict=True)]
    totals = results['totals']
    observed = sum(sum(rows) for rows in differences.values())
    if (observed != totals[NONLOSS]['holdoutPasses'] - totals[STRICT]['holdoutPasses']
            or counts['lookupDelta'] != totals[NONLOSS]['paidLookups'] - totals[STRICT]['paidLookups']):
        raise ValueError('The paired audit must reproduce the cohort changes')
    rng = Random(plan['bootstrapSeed'])
    samples = [sum(sum(rng.choices(rows, k=len(rows))) for _, rows in sorted(differences.items()))
               for _ in range(plan['bootstrapDraws'])]
    return {**counts, 'holdoutPassDelta': observed, 'pairedRange95': transfer.study.math.interval(samples)}


def replay(plan, cohorts, reference):
    reports = {}
    with (patch.object(model_transfer, 'full_cap', full_cap), patch.object(model_transfer, 'CPO', METHODS)):
        for name, panels in cohorts.items():
            result = model_transfer.measure_cohort(plan, panels)
            reports[name] = {**result, 'trainingThresholdComparison': paired_change(plan, panels, result)}
    baseline = reports['previous-mmlu']
    if (any(baseline['totals'][arm] != reference['totals'][arm] for arm in baseline['totals'] if arm != NONLOSS)
            or baseline['comparisons'][STRICT] != reference['comparisons'][STRICT]
            or any(panel[STRICT] != reference['panelsAtOriginalCap'][name][STRICT]
                   for name, panel in baseline['panelsAtOriginalCap'].items())):
        raise ValueError('The previous strict policy and GEPA cost frontier must reproduce')
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, cohorts, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path, and pinned GEPA')
    report = replay(plan, cohorts, reference)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
