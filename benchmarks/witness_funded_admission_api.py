"""Verify the public funded admission API against every frozen retry decision."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_funded_native_comparison as native, witness_retry_funding as funding
from cpo import Row
from cpo._contract import digest
from cpo.halving import funded_admission
from cpo.rotating_witness.episode import WitnessCycle


ROOT, RANKING, retry = funding.ROOT, funding.RANKING, funding.retry
RECEIPT = 'docs/witness-funded-native-comparison-results-v1.json'
RECEIPT_SHA256 = '2ec98fdd7bcca098edaf539fd7ff2671331b5aa88106d832cd8ca3f873b4dac6'
THRESHOLDS = (12, 14)
METHODS = (funding.FULL, *(f'at-least-{threshold}' for threshold in THRESHOLDS))
FIELDS = ('holdoutPasses', 'paidLookups', 'proofLookups', 'proofCapped', 'promotions', 'retries', 'retryLookups',
          'retryPromotions')


def prepare():
    parent, funding_receipt, _, data = native.prepare()
    raw = (ROOT / RECEIPT).read_bytes()
    if sha256(raw).hexdigest() != RECEIPT_SHA256 or json.loads(raw)['planSha256'] != digest(parent):
        raise ValueError('Use the published paired native comparison and funding receipt')
    plan = {'protocol': 'witness-funded-admission-api-v1', 'parentPlanSha256': digest(parent),
            'parentReceiptSha256': RECEIPT_SHA256,
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'apiSha256': sha256(Path(funded_admission.__file__).read_bytes()).hexdigest(),
            'jointProofCap': funding.CAP, 'fallbackValidationCap': parent['fallbackValidationCap'],
            'thresholds': THRESHOLDS,
            'scope': 'Replay the full first proof and both funded retry thresholds. Match each admission '
                     'decision, callback sequence, and charged lookup count before aggregating holdout.'}
    return plan, funding_receipt, data


def outcomes(matrix, held, start, layouts, plan, policy, nomination):
    recorded = []
    scalar = retry.scalar_proof

    def trace(*args, **kwargs):
        result = scalar(*args, **kwargs)
        recorded.append(result)
        return result

    with patch.multiple(retry, scalar_proof=trace, METHODS=funding.METHODS):
        expected = funding.outcomes(matrix, held, start, layouts, plan, policy, nomination)
    first = None
    if recorded:
        first = recorded[-2] if expected[funding.EXACT].retry else recorded[-1]
    cycles = tuple(WitnessCycle(tuple(layout['alternatives']), tuple(Row(str(case), 'task') for case in layout['validation']),
                                tuple(Row(str(case), 'task') for case in layout['qualify']), layout['seed'])
                   for layout in layouts)
    grades = {(prompt, str(case)): passed for (prompt, case), passed in nomination.grades.items()}
    results = {funding.FULL: expected[funding.FULL]}
    for threshold in THRESHOLDS:
        callbacks = []

        def evaluate(prompt, row, repeat):
            passed = matrix[int(prompt)][int(row.id)] == '1'
            callbacks.append((prompt, row.id, repeat, passed))
            return passed

        measured = funded_admission.qualify_with_funded_retry(
            start, nomination.original, cycles, evaluate, grades, minimum_retry_lookups=threshold,
            evaluation_limit=funding.CAP, maximum_extension_rows=plan['maximumExtensionRows'],
            minimum_gain=plan['minimumQualificationGain'])
        key = f'at-least-{threshold}'
        prior = expected[key]
        second = recorded[-1] if prior.retry else None
        if measured.first != first or measured.retry != second:
            raise ValueError('The public API changed the first or second exact proof receipt')
        expected_calls = [(row.prompt, row.row_id, row.repeat, row.passed)
                          for proof in (first, second) if proof is not None for row in proof.observations]
        if callbacks != expected_calls:
            raise ValueError('The public API changed the charged callback sequence')
        last = measured.retry or measured.first
        result = retry.Decision(measured.prompt, measured.qualification_evaluations,
                                last.status if last is not None else 'no-nominee',
                                second is not None, len(second.observations) if second is not None else 0)
        if result != prior:
            raise ValueError('The public API changed a published retry decision or lookup charge')
        results[key] = result
    return results


def execute(plan, reference, data):
    with patch.multiple(retry, METHODS=METHODS, outcomes=outcomes):
        replayed = {phase: retry.measure(*data[phase], plan['fallbackValidationCap']) for phase in RANKING.PHASES}
    cohorts = {}
    for phase, (groups, traces) in replayed.items():
        totals = {}
        for method in METHODS:
            sums = sum((group['counts'][method] for group in groups.values()), Counter())
            totals[method] = {key: sums[key] for key in FIELDS}
            if totals[method] != reference['cohorts'][phase]['totals'][method]:
                raise ValueError(f'The archived score or cost changed for {phase}/{method}')
        cohorts[phase] = {'episodes': sum(group['decisionsPerCase'] for group in groups.values()),
                          'totals': totals, 'panelTraceSha256': traces}
    return {'plan': plan, 'planSha256': digest(plan), 'cohorts': cohorts, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
