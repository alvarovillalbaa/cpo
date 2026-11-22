"""Verify the public prechecked certificate cycle against the frozen CPO paths."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_paid_qualification_margin_route as source
from cpo import Observation, Row
from cpo import prechecked_certificate_cycle as api
from cpo._contract import digest


prior = source.prior
RECEIPT = 'docs/recorded-paid-qualification-margin-route-results-v1.json'
RECEIPT_SHA256 = '81f92caf936a3b91095d75773a72103875ee2cc9eb909dc7e5a6282bfe7febf2'


def prepare():
    parent, groups, _ = source.prepare()
    receipt = prior.cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, parent)
    paths = (Path(__file__), Path(api.__file__))
    plan = {**{key: parent[key] for key in ('caseCounts', 'seeds', 'challengers', 'screenCap')},
            'protocol': 'prechecked-certificate-cycle-replay-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'minimumGains': (1, 2),
            'scope': 'Replace the experimental screen and ordered independent proof with the public '
                     'cycle. Compare both fixed margins on all archived panels, including the exact '
                     'order, identities and grades of paid callbacks.'}
    return plan, groups, receipt['results']


def reference_path(args, cap, minimum):
    cells, incumbent, _, cohorts, _ = args
    selector = prior.early.select
    certify = prior.adapter.qualify_with_prefix if minimum == 1 else prior.minimum_two
    validation, proof = [], []

    def capture_search(incumbent, candidates, rows, observe, ledger, **settings):
        chosen = selector(incumbent, candidates, rows, observe, ledger, **settings)
        validation.extend(('validation', prompt, case, result.passed)
                          for (prompt, case), result in ledger.items())
        return chosen

    def capture_proof(*args):
        decision = certify(*args)
        proof.extend(('qualification', item.prompt, item.row_id, item.passed) for item in decision.observations)
        return decision

    with (patch.object(prior.early, 'select', capture_search),
          patch.object(prior.adapter, 'qualify_with_prefix', capture_proof)):
        point, trace, grades, _ = prior.early.trial(args, 'complete-panel', cap)
    prefix = [('qualification', incumbent, str(case), bool(cells[incumbent][case][0]))
              for case in cohorts[2][:point['precheckLookups']]]
    if proof and proof[:len(prefix)] != prefix:
        raise ValueError('The charged incumbent precheck must be the qualification prefix')
    return (point, trace, grades), [*prefix, *validation, *proof[len(prefix):]]


def verify_path(args, cap, minimum):
    cells, start, roster, cohorts, seed = args
    validation = tuple(Row(str(case), 'validation') for case in cohorts[1])
    qualification = tuple(Row(str(case), 'qualification') for case in cohorts[2])
    called = []

    def evaluate(prompt, row):
        passed = bool(cells[prompt][int(row.id)][0])
        called.append(('validation', prompt, row.id, passed))
        return Observation(passed, {})

    def qualify(prompt, row, repeat):
        if repeat:
            raise ValueError('The archived proof uses one exact observation per case')
        passed = bool(cells[prompt][int(row.id)][0])
        called.append(('qualification', prompt, row.id, passed))
        return passed

    result = api.run_prechecked_certificate_cycle(start, roster, validation, qualification, evaluate,
                                                  metric_limit=cap, qualify=qualify, minimum_gain=minimum, seed=seed)
    (original, trace, grades), expected = reference_path(args, cap, minimum)
    heldout = tuple(cells[result.prompt][case][0] for case in cohorts[-1])
    proof = [('qualification', item.prompt, item.row_id, item.passed) for item in result.qualification.observations]
    if (called != expected or result.search.prompt != trace[2] or result.prompt != trace[3]
            or heldout != grades or result.search.evaluations != original['searchLookups']
            or proof != [item for item in called if item[0] == 'qualification']
            or result.qualification_evaluations != original['qualificationLookups']
            or result.search.evaluations + result.qualification_evaluations != original['paidLookups']):
        raise ValueError('The public cycle must reproduce the sealed paid path and deployment')
    return {'holdoutPasses': sum(heldout), 'paidLookups': len(called)}, called, trace


def replay(plan, groups, reference):
    results = {}
    for cohort, panels in groups.items():
        totals, checks = {}, {}
        for subject, model, matrix in panels:
            cells = {str(index): tuple((int(passed), None, False) for passed in row)
                     for index, row in enumerate(matrix)}
            paths, original = {}, {}
            for seed in plan['seeds']:
                start, roster, cohorts = prior.transfer.fixed.archive.transfer.schedule(
                    subject, len(matrix[0]), len(matrix), seed, plan)
                for minimum, label in zip(plan['minimumGains'], (source.ONE, source.TWO), strict=True):
                    point, called, trace = verify_path((cells, start, roster, cohorts, seed), plan['screenCap'], minimum)
                    totals.setdefault(label, Counter()).update(point)
                    paths.setdefault(label, []).append(digest(called))
                    original.setdefault(label, []).append(trace)
            panel = f'{subject}/{model}'
            anchored = reference[cohort]['panels'][panel]['traceSha256']
            if any(digest(traces) != anchored[label] for label, traces in original.items()):
                raise ValueError('The reference must match both archived fixed-margin panel traces')
            checks[panel] = {label: digest(trace) for label, trace in paths.items()}
        if any(point != reference[cohort]['totals'][label] for label, point in totals.items()):
            raise ValueError('Both fixed margins must reproduce the archived aggregate scores and costs')
        results[cohort] = {'totals': totals, 'panelPathHashes': checks,
                           'pathsChecked': len(panels) * len(plan['seeds']) * len(plan['minimumGains'])}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, groups, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh output path')
    report = replay(plan, groups, reference)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
