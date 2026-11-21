"""Transfer a training-corroboration route from language to math archives."""

import argparse
from collections import Counter
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_expected_training_order as parent
from benchmarks import recorded_first_certificate_transfer as donor
from benchmarks import recorded_margin_corroboration as margin
from cpo import Row
from cpo._contract import digest


transfer, math, core = parent.math_transfer, parent.math, parent.core
adapter = core.parent
REFERENCE = 'docs/recorded-expected-training-order-results-v1.json'
REFERENCE_SHA256 = '49a761d5acc0b549855e9a51b8ee47243ab4e9ec2767a7875e65b0adc3e91329'
MARGIN_REFERENCE = 'docs/recorded-margin-corroboration-results-v1.json'
MARGIN_SHA256 = '49d5266bfb32213c65b2f069676b3c394a2562df83a574702d55a861b1f337ad'
NEVER = 'never-training'
ALWAYS = 'always-training'
ARM = 'calibrated-training-route'
METHODS = (ARM, parent.ORDERED, core.FIRST)
STRATA = ('one-clean', 'one-mixed', 'multiple-clean', 'multiple-mixed')
MINIMUM_DONOR_TRIALS = 8


def stratum(old, new):
    pairs = tuple(zip(old, new, strict=True))
    gain = sum(after - before for before, after in pairs)
    if gain <= 0:
        raise ValueError('Expected a strictly improving validation nominee')
    return ('one-' if gain == 1 else 'multiple-') + (
        'mixed' if any(before and not after for before, after in pairs) else 'clean')


def run_trial(cells, start, roster, cohorts, seed, cap, route):
    original_select, original_proof = math.select, adapter.qualify_with_prefix
    training = tuple(Row(str(case), 'training') for case in cohorts[0][:len(cohorts[0]) // 2])
    state, audit = {}, Counter()
    bucket = None

    def select(incumbent, candidates, rows, observe, ledger, **kwargs):
        result = original_select(incumbent, candidates, rows, observe, ledger, **kwargs)
        state.update(validation=rows, observe=observe, ledger=ledger)
        return result

    def qualify(incumbent, challenger, rows, read, prefix, counts, proof_seed, mode):
        nonlocal bucket
        decision = original_proof(incumbent, challenger, rows, read, prefix, counts, proof_seed, mode)
        if decision.status != 'promoted':
            return decision
        validation, ledger = state['validation'], state['ledger']
        old, new = ([ledger[prompt, row.id].passed for row in validation] for prompt in (incumbent, challenger))
        bucket = stratum(old, new)
        if bucket not in route:
            return decision

        before = len(ledger)
        if before + 2 * len(training) > cap:
            raise ValueError('The frozen replay must fund a complete training proof')
        rates, prices = parent.estimate((incumbent, challenger), validation, ledger, cells)
        supported = parent.settle((incumbent, challenger), training, state['observe'], ledger,
                                  rates, prices, minimum_gain=1)
        audit.update(trainingChecks=1, trainingVetoes=int(not supported), trainingLookups=len(ledger) - before)
        return decision if supported else replace(decision, status='rejected', prompt=incumbent)

    # Keep the original strict validation nominee. Only the signed qualification
    # result can trigger training, so the route cannot affect the proof's reads.
    with (patch.object(math, 'select', select), patch.object(adapter, 'qualify_with_prefix', qualify),
          patch.object(core.prior, 'can_defer', lambda *_: False),
          patch.object(core.backup, 'select_with_training', lambda _, first, *args, **kwargs: first)):
        point, trace, grades = adapter.run_trial(cells, start, roster, cohorts, seed, cap,
                                                 parent.BASELINE, adapter.EXPECTED)
    if point['searchLookups'] > cap or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']:
        raise ValueError('The route must charge all lookups within the existing allowances')
    return {**point, **audit}, trace, grades, bucket


def fit(evidence):
    """Enroll well-supported strata with positive mean normalized donor gain."""
    if not evidence:
        raise ValueError('The predeclared donor families are required')
    return tuple(bucket for bucket in STRATA if all(family[bucket]['trials'] >= MINIMUM_DONOR_TRIALS
                                                    for family in evidence.values()) and sum(
        Fraction(family[bucket]['holdoutPassDelta'], family[bucket]['heldoutGrades'])
        for family in evidence.values()) > 0)


def calibrate(plan, panels):
    evidence = {family: {bucket: Counter() for bucket in STRATA} for family, *_ in panels}
    for family, subject, _, matrix in panels:
        cells = {str(index): tuple((int(passed), None, False) for passed in vector)
                 for index, vector in enumerate(matrix)}
        for seed in plan['seeds']:
            start, roster, cohorts = donor.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
            args = (cells, start, roster, cohorts, seed, plan['searchCap'])
            before, old, old_grades, bucket = run_trial(*args, ())
            if bucket is None:
                continue
            after, trace, grades, checked = run_trial(*args, STRATA)
            if checked != bucket or trace[:3] != old[:3] or after['qualificationLookups'] != before['qualificationLookups']:
                raise ValueError('Donor calibration must compare the same nomination and qualification')
            evidence[family][bucket].update(trials=1, heldoutGrades=len(grades),
                                            holdoutPassDelta=sum(grades) - sum(old_grades),
                                            addedLookups=after['paidLookups'] - before['paidLookups'],
                                            trainingVetoes=after['trainingVetoes'])
    return evidence


def prepare():
    inherited, data, controls, _ = parent.prepare()
    reference = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    margin_plan, _, _ = margin.prepare()
    proof_reference = transfer.cost.prior.baseline.read_reference(MARGIN_REFERENCE, MARGIN_SHA256, margin_plan)
    donor_plan, panels = donor.prepare()
    evidence = calibrate(donor_plan, panels)
    route = fit(evidence)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-calibrated-training-route-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'strictRouteReceiptSha256': MARGIN_SHA256,
            'donorPlanSha256': digest(donor_plan), 'donorEvidenceSha256': digest(evidence), 'route': route,
            'strata': STRATA, 'minimumQualifiedDonorTrialsPerFamily': MINIMUM_DONOR_TRIALS,
            'methods': (*METHODS, ALWAYS, NEVER), 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'Use only paid validation gain and the presence of an incumbent pass lost on validation. '
                     'Train the route on the fixed BBH, LMentry and MMLU donor panels. Require eight episodes '
                     'per donor family and a positive sum of per-family normalized veto gains. Freeze the '
                     'route before replaying target outcomes. Use the seeded strict nominee and shared early '
                     'qualification. Compare against always and never checking training, and reproduce '
                     'the original CPO and GEPA cost frontiers.'}
    return plan, data, controls, reference['results'], proof_reference['results'], evidence


def measure(plan, cells, settings, group, width, controls, reference, proof_reference):
    totals = {name: Counter() for name in (ALWAYS, NEVER)}
    by_stratum = {name: Counter() for name in STRATA}

    def trial(*args):
        args = args[:-1]
        before, old, original_grades, bucket = run_trial(*args, ())
        after, new, new_grades, checked = run_trial(*args, STRATA)
        if checked != bucket or new[:3] != old[:3] or after['qualificationLookups'] != before['qualificationLookups']:
            raise ValueError('Training must preserve the validation and independent qualification path')
        totals[NEVER].update(before)
        totals[ALWAYS].update(after)
        if bucket is not None:
            by_stratum[bucket].update(trials=1, holdoutPassDelta=sum(new_grades) - sum(original_grades),
                                      addedLookups=after['paidLookups'] - before['paidLookups'],
                                      trainingVetoes=after['trainingVetoes'])
        return (after, new, new_grades) if bucket in plan['route'] else (before, old, original_grades)

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
            or any(totals[arm]['holdoutPasses'] != proof_reference['totals'][source]['holdoutPasses']
                   for arm, source in ((NEVER, 'strict-precheck'), (ALWAYS, 'training-only')))):
        raise ValueError('The original lookup frontiers and both fixed-route held-out results must reproduce')
    return {'totals': {ARM: result['anchors'][ARM], **totals}, 'trainingEffectByStratum': by_stratum,
            'comparisons': {key: value[ARM] for key, value in result['comparisons'].items()}}


def replay(plan, data, controls, reference, proof_reference, evidence):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = measure(plan, cells, settings, group, width, controls[dataset][name],
                                                 reference[dataset][name], proof_reference[dataset][name])
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'donorEvidence': evidence, 'results': results}


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
