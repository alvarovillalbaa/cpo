"""Test an exact incumbent training precheck before a paid validation race."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_expected_training_order as parent
from cpo import Row
from cpo._contract import digest


transfer, math, core = parent.math_transfer, parent.math, parent.core
REFERENCE = 'docs/recorded-expected-training-order-results-v1.json'
REFERENCE_SHA256 = '49a761d5acc0b549855e9a51b8ee47243ab4e9ec2767a7875e65b0adc3e91329'
TRAINING_FIRST = 'incumbent-training-precheck'
VALIDATION_FIRST = 'incumbent-validation-then-training-precheck'
MODES = (TRAINING_FIRST, VALIDATION_FIRST)


def precheck(incumbent, roster, validation, training, observe, ledger, *, mode, cap, audit):
    """Return true when one of the existing strict gains is impossible."""
    # The original policy can buy full validation and check up to two challengers.
    # Leave its funding decisions unchanged, including the incumbent's training reserve.
    if not training or len(ledger) + (1 + len(roster)) * len(validation) + 3 * len(training) > cap:
        return False

    def perfect(rows, name):
        before = len(ledger)
        passed = all(observe(incumbent, row).passed for row in rows)
        audit[name + 'Lookups'] += len(ledger) - before
        audit[name + 'Stops'] += int(passed)
        return passed

    return ((mode == VALIDATION_FIRST and perfect(validation, 'validationPrecheck'))
            or perfect(training, 'trainingPrecheck'))


def run_trial(cells, start, roster, cohorts, seed, cap, mode):
    original = math.select
    training = tuple(Row(str(case), 'training') for case in cohorts[0][:len(cohorts[0]) // 2])
    audit = Counter()

    def select(incumbent, roster, validation, observe, ledger, *, method, cap):
        if precheck(incumbent, roster, validation, training, observe, ledger, mode=mode, cap=cap, audit=audit):
            return incumbent, False

        # The original selector meters reads within this race. The paid ledger
        # reuses any already bought replies and still tracks the whole trial.
        race = {}

        def read(prompt, row):
            grade = observe(prompt, row)
            race[prompt, row.id] = grade
            return grade

        return original(incumbent, roster, validation, read, race, method=method, cap=cap)

    with patch.object(math, 'select', select):
        point, trace, grades = parent.run_trial(cells, start, roster, cohorts, seed, cap)
    if point['searchLookups'] > cap or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']:
        raise ValueError('Incumbent prechecks must be fully charged within the existing limits')
    return {**point, **audit}, trace, grades


def prepare():
    inherited, data, controls, _ = parent.prepare()
    archived = transfer.cost.prior.baseline.read_reference(REFERENCE, REFERENCE_SHA256, inherited)
    plan = {**{key: inherited[key] for key in ('datasets', 'incumbentGroups', 'challengerCounts', 'searchCap',
                                               'gepaVersion', 'bootstrapSeed', 'bootstrapDraws')},
            'protocol': 'recorded-incumbent-training-precheck-v1', 'parentPlanSha256': digest(inherited),
            'parentReceiptSha256': REFERENCE_SHA256, 'methods': (*MODES, parent.ORDERED),
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope': 'After the original qualification precheck, stop before the candidate race if the '
                     'incumbent is perfect on its existing training half. Compare training first with '
                     'checking validation headroom before training. Buy each reply once and preserve '
                     'the original cap, deployment and held-out grades. Reuse the pinned GEPA frontiers.'}
    return plan, data, controls, archived['results']


def measure(plan, cells, settings, group, width, controls, reference, mode):
    changes = Counter()

    def trial(*args):
        args = args[:-1]
        before, original_trace, original_grades = parent.run_trial(*args)
        after, trace, grades = run_trial(*args, mode)
        if trace[3] != original_trace[3] or grades != original_grades:
            raise ValueError('Checking incumbent headroom changed a deployment or held-out grade')
        if not any(after.get(name) for name in ('validationPrecheckStops', 'trainingPrecheckStops')):
            if trace[2] != original_trace[2] or after['qualificationLookups'] != before['qualificationLookups']:
                raise ValueError('An unsuccessful precheck changed the original nomination or qualification')
        saved = before['paidLookups'] - after['paidLookups']
        changes.update(trials=1, savedLookups=saved, cheaper=int(saved > 0), dearer=int(saved < 0))
        if transfer.HISTORICAL in before:
            changes['savedHistoricalCostNanodollars'] += before[transfer.HISTORICAL] - after[transfer.HISTORICAL]
        return after, trace, grades

    def original(*args):
        return parent.run_trial(*args[:-1])

    anchors = {**controls, 'totals': {**controls['totals'], parent.ORDERED: reference['anchors'][parent.ORDERED]}}
    with (patch.object(transfer, 'PRIMARY', mode), patch.object(transfer, 'METHODS', (mode, parent.ORDERED)),
          patch.object(core, 'trial', original), patch.object(transfer.parity.shortlist, 'trial', trial)):
        result = transfer.measure(plan, cells, settings, group, width, anchors)
    if (any(point != reference['totals'][label] for label, point in result['totals'].items() if label != mode)
            or any(value[parent.ORDERED] != reference['comparisons'][key][parent.ORDERED]
                   for key, value in result['comparisons'].items())
            or changes['savedLookups'] != reference['totals'][parent.ORDERED]['paidLookups']
            - result['totals'][mode]['paidLookups']):
        raise ValueError('The replay must reproduce the original costs, results, and matched GEPA frontier')
    return {'totals': result['anchors'][mode], 'pairedChanges': changes,
            'comparisons': {key: value[mode] for key, value in result['comparisons'].items()}}


def replay(plan, data, controls, reference):
    results = {}
    for dataset, settings in plan['datasets'].items():
        cells = math.load_cells(dataset, data[dataset]['record'])
        results[dataset] = {}
        for group in plan['incumbentGroups']:
            for width in plan['challengerCounts']:
                name = f'{group}/{width}'
                results[dataset][name] = {mode: measure(plan, cells, settings, group, width, controls[dataset][name],
                                                          reference[dataset][name], mode) for mode in MODES}
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
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
