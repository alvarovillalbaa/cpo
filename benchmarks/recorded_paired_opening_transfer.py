"""Test the packaged exact opening proof on the recorded ARC and AIME cohorts."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_opening_dominance_transfer as prior
from cpo._contract import digest
from cpo.paired_opening import run_paired_opening_cycle


METHOD = 'paired-opening'
CAPS = {METHOD: (3, 1), 'paired-opening-cap-2x': (2, 1), 'paired-opening-cap-2.5x': (5, 2)}
CONTROL_REVISION = '100c8697f6ed3fe3959d7c9cab91b49f9cf277f7'
REFERENCE = prior.ROOT / 'docs/recorded-opening-dominance-transfer-results-v1.json'
REFERENCE_SHA = 'd55d3dccc80b27ec2058e66c54924bfbd61af31c2383955e4d600edc7a1eb24e'
CONTROLS = (prior.BASELINE, prior.CANDIDATE, *prior.CONTROLS)
ARMS = (*CAPS, *CONTROLS)


def prepare():
    base, data = prior.prepare()
    raw = REFERENCE.read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or reference['planSha256'] != digest(base):
        raise ValueError(f'Replay the sealed controls from {CONTROL_REVISION} with the paired-opening source overlay')
    files = ('benchmarks/recorded_paired_opening_transfer.py', 'cpo/paired_opening/__init__.py')
    plan = {
        'protocol': 'recorded-paired-opening-transfer-v1', 'controlRevision': CONTROL_REVISION,
        'priorPlanSha256': digest(base),
        'priorResultSha256': REFERENCE_SHA, 'methods': list(ARMS), 'gepaVersion': base['gepaVersion'],
        'primary': METHOD, 'proofBudgetPerValidationCase': CAPS,
        'exploratoryFollowups': list(CAPS)[1:],
        'datasets': base['datasets'], 'incumbentGroups': base['incumbentGroups'], 'corpusSha256': base['corpusSha256'],
        'sourceSha256': {path: sha256((prior.ROOT / path).read_bytes()).hexdigest() for path in files},
        'gate': ('More pooled held-out passes at no greater cost, or equal passes with at least 10 percent savings. '
                 'Use recorded evaluator charges on ARC and paid reads on AIME. Report paired losses separately.'),
    }
    return plan, data, reference['results']


def package_adapter(incumbent, _train, validation, admission, evaluate, *, opening_pair, metric_limit,
                    qualify, seed, scale, **_):
    # Let the shared benchmark execute the actual admission once for each method.
    numerator, denominator = scale
    cap = (numerator * len(validation) + denominator - 1) // denominator
    return run_paired_opening_cycle(incumbent, validation, admission, evaluate, opening_pair=opening_pair,
                                    metric_limit=min(cap, metric_limit), qualify=qualify, seed=seed,
                                    qualification_limit=0)


def measure_group(cells, settings, starts, expected):
    size = len(next(iter(cells.values())))
    totals = {method: Counter() for method in ARMS}
    traces = {method: [] for method in ARMS}
    comparisons = {arm: {control: Counter() for control in CONTROLS} for arm in CAPS}
    differences = {arm: {control: [0] * size for control in CONTROLS} for arm in CAPS}
    for seed in settings['seeds']:
        cohorts = prior.split_cases(size, seed, settings['cohorts'])
        for incumbent in starts:
            choices = [prompt for prompt in cells if prompt != incumbent]
            pair = Random(f'{seed}/{incumbent}').sample(choices, len(choices))[:2]
            trials = {method: prior.trial(cells, incumbent, pair, cohorts, seed, method) for method in CONTROLS}
            for arm, scale in CAPS.items():
                with patch.object(prior, 'run_opening_screen_cycle', partial(package_adapter, scale=scale)):
                    trials[arm] = prior.trial(cells, incumbent, pair, cohorts, seed, prior.BASELINE)
            for method, record in trials.items():
                totals[method].update(record['totals'])
                traces[method].append([seed, incumbent, pair, record])
            for arm, by_control in comparisons.items():
                selected = trials[arm]
                for control, counts in by_control.items():
                    reference = trials[control]
                    counts['nomineeChanges'] += reference['nominee'] != selected['nominee']
                    counts['admittedPromptChanges'] += reference['selected'] != selected['selected']
                    for case, before, after in zip(cohorts[-1], reference['passed'], selected['passed'], strict=True):
                        differences[arm][control][case] += after - before
                        counts['pairedLosses'] += after < before

    receipts = {method: {**total, 'traceSha256': digest(traces[method])} for method, total in totals.items()}
    if any(receipts[method] != expected['totals'][method] for method in CONTROLS):
        raise ValueError('A native or CPO control changed its recorded counts or trace')
    charge = 'historicalCostNanodollars' if 'historicalCostNanodollars' in totals[METHOD] else 'paidReads'
    for arm, by_control in comparisons.items():
        for control, counts in by_control.items():
            deltas = differences[arm][control]
            delta = sum(deltas)
            cost, baseline = totals[arm][charge], totals[control][charge]
            by_control[control] = {
                **counts, 'passDelta': delta, 'paidReadDelta': totals[arm]['paidReads'] - totals[control]['paidReads'],
                'costMetric': charge, 'costDelta': cost - baseline,
                'caseResampling95PassDifference': prior.case_resampling_range((deltas,)),
                'qualifies': delta > 0 and cost <= baseline or delta == 0 and 10 * cost <= 9 * baseline,
            }
    return {'pathsPerArm': len(traces[METHOD]), 'heldoutUsesPerArm': expected['heldoutUsesPerArm'],
            'totals': receipts, 'comparisons': comparisons}


def measure(plan, data, reference):
    results = {}
    for task, settings in plan['datasets'].items():
        cells = prior.load_cells(task, data[task]['record'])
        starts = tuple(cells)
        results[task] = {
            group: measure_group(cells, settings, starts[:1] if group == 'root' else starts[1:], reference[task][group])
            for group in plan['incumbentGroups']
        }
    return {'plan': plan, 'planSha256': digest(plan), 'results': results, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Use the current seal, GEPA 0.1.4, and a fresh output path')
    result = measure(plan, data, reference)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
