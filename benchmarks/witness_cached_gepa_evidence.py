"""Pair the cache-routed CPO archive against the full affordable native GEPA grid."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_mmlu_witness_fallback as replay
from benchmarks import witness_cached_halving as cached
from cpo._contract import digest
from cpo.halving.cached_lookahead import CachedLookaheadHalving


ROOT = replay.ROOT
BBH = 'bbh-lmentry'
PHASES = (BBH, *replay.PHASES)
RECEIPT = 'docs/witness-cached-halving-results-v1.json'
RECEIPT_SHA256 = 'dba915e27ff5a540fc96ffd5f6a12a59940f7e822080eee7a58a87a9e9b42ee4'


def prepare():
    upstream, _, (refs, bbh, mmlu, native) = cached.prepare()
    raw = (ROOT / RECEIPT).read_bytes()
    receipt = json.loads(raw)
    if sha256(raw).hexdigest() != RECEIPT_SHA256 or receipt['planSha256'] != digest(upstream):
        raise ValueError('Use the exact published cache-route comparison')
    mmlu_receipt = refs[cached.previous.routing.MMLU_REPORT]
    inputs, panels, prior = bbh
    settings = {arm: config for arm, config in native['plan']['conditions'].items() if arm.startswith('gepa-')}
    data = {BBH: (inputs, panels, native['panels'], settings, prior['plan']['conditions'][replay.BASE]['searchCap'])}
    design, inputs, cohorts, _ = mmlu
    for phase, panels in cohorts.items():
        data[phase] = (inputs, panels, mmlu_receipt['phases'][phase]['panels'],
                       design['nativeSettings'], design['baseSearchCap'])
    sources = (Path(__file__).resolve(), Path(replay.__file__).resolve(), Path(replay.native.__file__).resolve(),
               Path(replay.paired.__file__).resolve())
    plan = {'protocol': 'witness-cached-gepa-paired-v1', 'parentPlanSha256': digest(upstream),
            'cacheRouteReceiptSha256': RECEIPT_SHA256, 'nativeReceipts': upstream['archiveReferences'],
            'nativeBBHAndLMentrySha256': upstream['nativeBBHAndLMentrySha256'],
            'sourceSha256': {**upstream['sourceSha256'], **{
                path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest() for path in sources}},
            'cohorts': {phase: sorted({panel['subject'] for panel in data[phase][1]}) for phase in PHASES},
            'nativeSettings': {phase: data[phase][3] for phase in PHASES},
            'draws': upstream['pairedCaseDraws'], 'seed': upstream['resamplingSeed'], 'fallbackValidationCap': 16,
            'gate': 'Require a positive subject-and-case lower endpoint against reselected affordable native GEPA '
                    'on each cohort. Count retention as a zero-cost native control.'}
    return plan, receipt, data


def measure(inputs, panels, expected, settings, cap):
    groups = {}
    plan = {'baseSearchCap': cap, 'nativeSettings': settings}
    controls = (replay.START, *settings)
    for panel in panels:
        if 'caseIDs' in panel:
            case_ids = panel['caseIDs']
            if len(set(case_ids)) != len(case_ids):
                raise ValueError('Physical case IDs must be unique in a model panel')
            panel = {**panel, 'caseOrderSha256': digest(case_ids)}
        key, outcome = replay.measure_panel(panel, plan, inputs, expected, groups)
        for arm in controls:
            recorded = expected[key][arm]
            fields = ('holdoutPasses', 'paidLookups', 'traceSha256')
            if any(outcome[arm][name] != recorded[name] for name in fields if name in recorded):
                raise ValueError(f'Native GEPA replay differed for {key}/{arm}')
    return groups


def summarize(groups, controls, plan):
    candidate, native = replay.CANDIDATE, (replay.START, *controls)
    arms = (candidate, *native)
    totals = {}
    for arm in arms:
        passes = [sum(item['cases'][arm]) for item in groups.values()]
        scores = [Fraction(passed, len(unit['caseIds']) * unit['decisionsPerCase'])
                  for passed, unit in zip(passes, groups.values(), strict=True)]
        totals[arm] = {'holdoutPasses': sum(passes), 'macroAccuracy': str(sum(scores) / len(scores)),
                       'paidLookups': sum(item['paidLookups'][arm] for item in groups.values())}
    with patch.multiple(replay.paired, CANDIDATE=candidate, NATIVE=native, POINTS=arms):
        best = replay.paired.affordable({arm: Fraction(row['macroAccuracy']) for arm, row in totals.items()},
                                         {arm: row['paidLookups'] for arm, row in totals.items()})
        draws = {axis: replay.paired.resample(groups, plan, resample_subjects=axis == 'subjectsAndCases')
                 for axis in ('casesWithinFixedSubjects', 'subjectsAndCases')}
        hindsight = replay.paired.native_allocation(groups, totals[candidate]['paidLookups'])
    interval = draws['subjectsAndCases']['comparisons']['best-affordable-gepa']['interval95PercentagePoints']
    return {'totals': totals, 'observedBestAffordableNative': best, 'pairedResampling': draws,
            'hindsightNativeAllocation': hindsight, 'distinctHoldoutCases': sum(len(g['caseIds']) for g in groups.values()),
            'subjects': len(groups), 'caseVotesSha256': digest(groups), 'qualifies': interval[0] > 0}


def execute(plan, receipt, data):
    if version('gepa') != '0.1.4':
        raise ValueError('Use hash-pinned GEPA 0.1.4')
    optimizer = import_module('gepa.optimize_anything')
    native_optimize = optimizer.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        train, hold = [replay.native.transfer.CaseRows({**row, 'id': row['case']} for row in rows)
                       for rows in (dataset, valset)]
        if train.by_id.keys() & hold.by_id.keys():
            raise ValueError('GEPA train and validation identities overlap')
        return native_optimize(*args, dataset=train, valset=hold, **settings)

    with (patch.object(optimizer, 'optimize_anything', disjoint),
          patch.multiple(replay, HALVING={}, HalvingSearch=CachedLookaheadHalving)):
        groups = {phase: measure(*data[phase]) for phase in PHASES}
    results = {phase: summarize(groups[phase], plan['nativeSettings'][phase], plan) for phase in PHASES}
    combined_mmlu = {subject: item for phase in replay.PHASES for subject, item in groups[phase].items()}
    if len(combined_mmlu) != sum(len(groups[name]) for name in replay.PHASES):
        raise ValueError('MMLU cohorts may not reuse a subject')
    results['mmlu-pooled'] = summarize(combined_mmlu, plan['nativeSettings'][replay.PHASES[0]], plan)
    for phase, scope in ((BBH, BBH), ('mmlu-pooled', 'mmlu')):
        prior = receipt['scopes'][scope]['points']['16']['lookahead']
        candidate = results[phase]['totals'][replay.CANDIDATE]
        if any(candidate[key] != prior[key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The cache-routed cap-16 score and cost did not reproduce')
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'cohorts': results,
            'qualifies': all(results[phase]['qualifies'] for phase in PHASES)}


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
