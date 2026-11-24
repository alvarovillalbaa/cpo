"""Replay backup ranking with only one forecast component recalibrated."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import continuous_backup_calibration as calibration
from cpo._contract import digest


continuous, transfer = calibration.continuous, calibration.transfer
FIT = 'docs/continuous-backup-calibration-fit-v1.json'
FIT_SHA = 'a267e624575ff5f8e68300b351724b1d3e846264db9a6ec54c02bacdd9750325'
RECEIPTS = dict(zip(continuous.COHORTS, (
    '250a0eb8cbc199f9d6026ea8187e99650fc8001f1a0de46b9a826a5e6653ce80',
    'ec6afd5761ebc1157c080230391fe1501c8985dcc249ccb2320c9302f280235f',
    '28f353cdfa449ad7388182096b4b29af9cf485b6eadff287de2f45f40a393694',
    '76773fa5ceb9127934160a17a9ad567708cf6eb69d21ae781dc71a1dbb394294',
    '4d8a6f4453972de52d54171b046b8e7364e6f94002decda264c1a15328072060',
    '339de9fb45f33f29a4f5218e917a6ae086cb6af98c4182ede5ec67bcfee60d0d',
    'c4d68ea2b39ec2844d471863efe2f96aefd93705f47d3a520012d1992cdef396',
), strict=True))
ORIGINAL_PREDICT = calibration.predict
BASELINES = calibration.RANKERS
COMPONENTS = {f'{method}-{component}': (method, component)
              for method in (calibration.EMPIRICAL, calibration.CORRECTED)
              for component in ('cost', 'probability')}
RANKERS = (*BASELINES, *COMPONENTS)


def predict(ranker, samples, context, baseline, quote, shrinkage):
    method, component = COMPONENTS.get(ranker, (ranker, None))
    probability, cost = ORIGINAL_PREDICT(method, samples, context, baseline, quote, shrinkage)
    if component == 'cost':
        return baseline[0], cost
    if component == 'probability':
        return probability, baseline[1]
    return probability, cost


def prepare(cohort):
    fit = transfer.read_locked(FIT, FIT_SHA)
    base, *inputs = calibration.prepare(cohort, fit)
    lock = RECEIPTS[cohort]
    parent = json.loads(transfer.read_locked(f'docs/continuous-backup-calibration-{cohort.lower()}-v1.json', lock))
    if parent['planSha256'] != digest(base):
        raise ValueError('The calibration source, fit and transfer design must match the original results')
    plan = {**base, 'protocol': 'continuous-backup-calibration-ablation-v1', 'calibrationReceiptSha256': lock,
            'sourceSha256': {**base['sourceSha256'], Path(__file__).name: sha256(Path(__file__).read_bytes()).hexdigest()},
            'rankers': RANKERS, 'forecastComponents': COMPONENTS,
            'scope': 'Freeze all backup evidence, examples, witnesses, prices, proof order and task allocation. '
                     'Reproduce the three original probability and cost estimates. For each frozen calibration '
                     'replace either probability or expected cost and keep the other original component. '
                     'Verify the unchanged component’s menu-wide error and replay matched simple controls '
                     'at each new realized spend. Use the same per-cohort upper bounds as the prior study.'}
    return plan, inputs, parent['results']


def measure(plan, inputs, reference):
    with patch.multiple(calibration, RANKERS=RANKERS, predict=predict):
        result = calibration.measure(plan, *inputs)
    for key, expected in reference['policies'].items():
        if digest(expected) != digest(result['policies'][key]):
            raise ValueError('Published calibration policies must reproduce their original dispatch and score')
    for mode, modeled in result['forecastErrorsInMillionths'].items():
        original = modeled[calibration.ORIGINAL]
        if any(digest(modeled[ranker]) != digest(reference['forecastErrorsInMillionths'][mode][ranker])
               for ranker in BASELINES):
            raise ValueError('Original and jointly calibrated forecast errors must reproduce')
        for ranker, (method, component) in COMPONENTS.items():
            replaced = 'absoluteCostError' if component == 'cost' else 'squaredError'
            expected = {**original, replaced: modeled[method][replaced]}
            if modeled[ranker] != expected:
                raise ValueError('Each ablation must change only its selected forecast component')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=continuous.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
