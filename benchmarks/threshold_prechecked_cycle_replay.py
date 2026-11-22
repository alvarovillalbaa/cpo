"""Compare qualification-aware prechecking on every archived screen path."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import prechecked_certificate_cycle_replay as original
from cpo import Observation, Row
from cpo import threshold_prechecked_cycle as api
from cpo._contract import digest


RECEIPT = 'docs/prechecked-certificate-cycle-replay-results-v1.json'
RECEIPT_SHA256 = '37ce185700edd9a7ee3bd0d8dbf2a05bf6586e64f31c1e877ebd441a0cb2fe77'


def prepare():
    parent, groups, _ = original.prepare()
    reference = original.prior.cost.prior.baseline.read_reference(RECEIPT, RECEIPT_SHA256, parent)
    paths = (Path(__file__), Path(api.__file__))
    plan = {**parent, 'protocol': 'threshold-prechecked-cycle-replay-v1',
            'parentPlanSha256': digest(parent), 'parentReceiptSha256': RECEIPT_SHA256,
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
            'scope': 'Test the public threshold precheck on both original qualification margins. '
                     'Continue paying for the incumbent only while the requested gain is attainable '
                     'and fewer than that number of misses are known. Credit the full prefix and '
                     'verify equal deployed prompts and held-out grades across all archived paths.'}
    return plan, groups, reference['results']


def run_trial(args, cap, minimum):
    original_point, original_calls, trace = original.verify_path(args, cap, minimum)
    cells, start, roster, cohorts, seed = args
    validation = tuple(Row(str(case), 'validation') for case in cohorts[1])
    proof = tuple(Row(str(case), 'qualification') for case in cohorts[2])
    called = []
    keys = set()

    def observe(role, prompt, row):
        key = role, prompt, row.id
        if key in keys:
            raise ValueError('A paid reply cannot be charged twice')
        keys.add(key)
        passed = bool(cells[prompt][int(row.id)][0])
        called.append((*key, passed))
        return passed

    def evaluate(prompt, row):
        return Observation(observe('validation', prompt, row), {})

    def qualify(prompt, row, repeat):
        if repeat:
            raise ValueError('The archived evaluation buys one reply per prompt and row')
        return observe('qualification', prompt, row)

    actual = api.run_threshold_prechecked_cycle(start, roster, validation, proof, evaluate, metric_limit=cap,
                                                 qualify=qualify, minimum_gain=minimum, seed=seed)
    if actual.prompt != trace[3]:
        raise ValueError('The threshold precheck cannot change which prompt is deployed')
    if minimum == 1 and called != original_calls:
        raise ValueError('One-gain qualification must reproduce the entire archived callback path')
    old_search = [item for item in original_calls if item[0] == 'validation']
    search = [item for item in called if item[0] == 'validation']
    paid_proof = [('qualification', item.prompt, item.row_id, item.passed)
                  for item in actual.qualification.observations]
    if (len(search) != actual.search.evaluations or len(search) > cap
            or paid_proof != [item for item in called if item[0] == 'qualification']
            or len(paid_proof) != actual.qualification_evaluations or len(paid_proof) > 2 * len(proof)):
        raise ValueError('The new path must account for every charged reply within the original budgets')
    if search and (search != old_search or actual.search.prompt != trace[2]):
        raise ValueError('The screen must reproduce its validation path whenever it runs')
    if old_search and not search and actual.qualification.upper_gain >= minimum:
        raise ValueError('Skipping a previously run search requires a paid impossibility bound')
    return original_point, original_calls, {
        'holdoutPasses': sum(cells[actual.prompt][case][0] for case in cohorts[-1]), 'paidLookups': len(called),
    }, {
        'pathsChecked': 1, 'cheaperTrials': int(len(called) < len(original_calls)),
        'dearerTrials': int(len(called) > len(original_calls)),
        'skippedSearches': int(bool(old_search) and not search),
        'validationLookupsSaved': len(old_search) - len(search),
        'qualificationLookupsSaved': len(original_calls) - len(old_search) - len(paid_proof),
    }, digest(called)


def replay(plan, groups, reference):
    results = {}
    labels = zip(plan['minimumGains'], (original.source.ONE, original.source.TWO), strict=True)
    arms = tuple(labels)
    for cohort, panels in groups.items():
        before, after, changes, details = {}, {}, {}, {}
        for subject, model, matrix in panels:
            cells = {str(index): tuple((int(passed), None, False) for passed in row)
                     for index, row in enumerate(matrix)}
            paths, original_paths = {}, {}
            for seed in plan['seeds']:
                start, roster, cohorts = original.prior.transfer.fixed.archive.transfer.schedule(
                    subject, len(matrix[0]), len(matrix), seed, plan)
                for minimum, label in arms:
                    old, old_calls, new, audit, path = run_trial((cells, start, roster, cohorts, seed),
                                                                plan['screenCap'], minimum)
                    before.setdefault(label, Counter()).update(old)
                    after.setdefault(label, Counter()).update(new)
                    changes.setdefault(label, Counter()).update(audit)
                    paths.setdefault(label, []).append(path)
                    original_paths.setdefault(label, []).append(digest(old_calls))
            panel = f'{subject}/{model}'
            if {label: digest(path) for label, path in original_paths.items()} != reference[cohort]['panelPathHashes'][panel]:
                raise ValueError('The original panel must exactly reproduce its published paid callback paths')
            details[panel] = {label: digest(path) for label, path in paths.items()}
        if before != reference[cohort]['totals']:
            raise ValueError('The original packaged screen and proof totals must reproduce')
        for label in before:
            saved = changes[label]['validationLookupsSaved'] + changes[label]['qualificationLookupsSaved']
            if (after[label]['holdoutPasses'] != before[label]['holdoutPasses']
                    or before[label]['paidLookups'] - after[label]['paidLookups'] != saved):
                raise ValueError('Reported cost savings and preserved quality must exactly reconcile')
        results[cohort] = {'original': before, 'thresholdPrecheck': after,
                           'changes': changes, 'panelPathHashes': details}
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
