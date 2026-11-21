"""Pair cross-family funded retries with the frozen affordable native GEPA grid."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import witness_cached_gepa_evidence as native, witness_retry_funding as funding
from cpo._contract import digest


ROOT, RANKING = funding.ROOT, funding.RANKING
PARENT = 'docs/witness-retry-funding-results-v1.json'
PARENT_SHA256 = 'aabc585765ed16cf0551a26a2f250cbf0ab4fdaff0be8ccd500bd5bcf9b8c2a4'
NATIVE_RECEIPT = 'docs/witness-cached-gepa-evidence-results-v1.json'
NATIVE_SHA256 = '83d5af833cc34a83598744ed94799ca04896fdfb4c0c73e9d38ea778884f6b39'
FUNDED, SINGLE = 'funded-retry', funding.FULL


def prepare():
    parent, _, data = funding.prepare()
    native_plan, _, native_data = native.prepare()
    raw, raw_native = (ROOT / PARENT).read_bytes(), (ROOT / NATIVE_RECEIPT).read_bytes()
    funded, controls = json.loads(raw), json.loads(raw_native)
    if (sha256(raw).hexdigest() != PARENT_SHA256 or funded['planSha256'] != digest(parent)
            or sha256(raw_native).hexdigest() != NATIVE_SHA256 or controls['planSha256'] != digest(native_plan)
            or data != native_data):
        raise ValueError('Both comparisons must use the published receipts and the same recorded episodes')
    plan = {'protocol': 'witness-funded-native-comparison-v1', 'parentPlanSha256': digest(parent),
            'nativePlanSha256': digest(native_plan), 'parentReceiptSha256': PARENT_SHA256,
            'nativeReceiptSha256': NATIVE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'fallbackValidationCap': parent['fallbackValidationCap'], 'nativeGEPAVersion': '0.1.4',
            'draws': native_plan['draws'], 'seed': native_plan['seed'], 'selectedGates': {
                phase: funded['cohorts'][phase]['selectedOutsideFamily'] for phase in native.PHASES},
            'method': 'Record both CPO policies and the full native grid on the same held-out case IDs. '
                      'Resample subjects and draw the same case indices for both sides. Reselect the strongest '
                      'native setting that fits the sampled CPO spend, including retaining the start.',
            'gate': 'The selected retry must have a positive lower paired endpoint against reselected native '
                    'GEPA and meet the seeded CPO cost on every enrolled cohort. Pooled MMLU is diagnostic.'}
    return plan, funded, controls, data


def measure(plan, phase, data):
    _, panels, _, _, _ = data
    per_matrix = {id(panel['correctness']): panel['subject'] for panel in panels}
    single = {}
    original = native.replay.original

    def select(matrix, held, start, layouts, active, policy):
        fixed = original.play(matrix, held, start, layouts, active, policy, original.witness)[:3]
        nominee = RANKING.search_to_nomination(matrix, held, start, layouts, active, policy,
                                               plan['fallbackValidationCap'])
        outcomes = funding.outcomes(matrix, held, start, layouts, active, policy, nominee)
        full = outcomes[SINGLE]
        subject = per_matrix[id(matrix)]
        account = single.setdefault(subject, {'held': held, 'votes': [0] * len(held), 'cost': 0, 'episodes': 0})
        if account['held'] != held:
            raise ValueError('The single proof must use the native holdout order')
        account['votes'] = [a + int(matrix[int(full.prompt)][case] == '1')
                            for case, a in zip(held, account['votes'], strict=True)]
        account['cost'] += nominee.paid_search + full.lookups
        account['episodes'] += 1
        selected = outcomes[plan['selectedGates'][phase]]
        return fixed, (selected.prompt, nominee.paid_search + selected.lookups, None), Counter()

    with patch.multiple(native.replay, CANDIDATE=FUNDED, HALVING={}, selection=select):
        groups = native.measure(*data)
    if groups.keys() != single.keys():
        raise ValueError('The single proof and native replay must have the same subjects')
    for subject, unit in groups.items():
        measured = single[subject]
        if unit['caseIds'] != measured['held'] or unit['decisionsPerCase'] != measured['episodes']:
            raise ValueError('The single proof and native replay must have the same physical cases and episodes')
        unit['cases'][SINGLE] = measured['votes']
        unit['paidLookups'][SINGLE] = measured['cost']
    return groups


def compare(groups, settings, plan, expected, reference, seeded_spend):
    controls = (native.replay.START, *settings)
    totals = {}
    for arm in (*controls, SINGLE, FUNDED):
        passes = [sum(group['cases'][arm]) for group in groups.values()]
        rates = [Fraction(count, len(group['caseIds']) * group['decisionsPerCase'])
                 for count, group in zip(passes, groups.values(), strict=True)]
        totals[arm] = {'holdoutPasses': sum(passes), 'macroAccuracy': str(sum(rates) / len(rates)),
                       'paidLookups': sum(group['paidLookups'][arm] for group in groups.values())}
        if arm in controls and totals[arm] != reference['totals'][arm]:
            raise ValueError(f'The frozen native total changed for {arm}')
        if arm not in controls and any(totals[arm][key] != expected[arm][key] for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError(f'The published CPO score or spend changed for {arm}')

    paired = native.replay.paired
    intervals = {}
    scores = {arm: Fraction(row['macroAccuracy']) for arm, row in totals.items()}
    costs = {arm: row['paidLookups'] for arm, row in totals.items()}
    for arm in (FUNDED, SINGLE):
        with patch.multiple(paired, CANDIDATE=arm, NATIVE=controls, POINTS=(arm, *controls)):
            fixed = paired.affordable(scores, costs)
            sample = paired.resample(groups, plan, resample_subjects=True)
            oracle = paired.native_allocation(groups, costs[arm])
        intervals[arm] = {'observedBestAffordableNative': fixed, 'pairedAgainstReselectedNative':
                          sample['comparisons']['best-affordable-gepa'], 'selectedNativeDraws':
                          sample['affordableSelections'], 'hindsightNativeAllocation': oracle}
    gate = intervals[FUNDED]['pairedAgainstReselectedNative']['interval95PercentagePoints']
    return {'totals': totals, 'comparisons': intervals, 'seededCPOPaidLookups': seeded_spend,
            'caseVotesSha256': digest(groups), 'qualifies': gate[0] > 0 and costs[FUNDED] <= seeded_spend}


def execute(plan, funded, controls, data):
    if version('gepa') != plan['nativeGEPAVersion']:
        raise ValueError('Use hash-pinned GEPA 0.1.4')
    optimizer = import_module('gepa.optimize_anything')
    original = optimizer.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        train, validation = [native.replay.native.transfer.CaseRows({**row, 'id': row['case']} for row in rows)
                             for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('Native GEPA train and validation IDs overlap')
        return original(*args, dataset=train, valset=validation, **settings)

    with patch.object(optimizer, 'optimize_anything', disjoint):
        groups = {phase: measure(plan, phase, data[phase]) for phase in native.PHASES}

    expected = {phase: {SINGLE: funded['cohorts'][phase]['totals'][SINGLE], FUNDED:
                        funded['cohorts'][phase]['totals'][plan['selectedGates'][phase]]} for phase in native.PHASES}
    seeded = {phase: funded['cohorts'][phase]['totals'][funding.retry.BASE]['paidLookups'] for phase in native.PHASES}
    reports = {phase: compare(groups[phase], data[phase][3], plan, expected[phase], controls['cohorts'][phase],
                              seeded[phase]) for phase in native.PHASES}
    mmlu = native.replay.PHASES
    if data[mmlu[0]][3] != data[mmlu[1]][3] or groups[mmlu[0]].keys() & groups[mmlu[1]].keys():
        raise ValueError('Pooled MMLU requires the same control grid and disjoint subjects')
    pool_expected = {arm: {key: sum(expected[phase][arm][key] for phase in mmlu)
                           for key in ('holdoutPasses', 'paidLookups')} for arm in (SINGLE, FUNDED)}
    pooled = compare({**groups[mmlu[0]], **groups[mmlu[1]]}, data[mmlu[0]][3], plan, pool_expected,
                     controls['cohorts']['mmlu-pooled'], sum(seeded[phase] for phase in mmlu))
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'cohorts': reports,
            'pooledMMLUDiagnostic': pooled, 'qualifies': all(row['qualifies'] for row in reports.values())}


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
