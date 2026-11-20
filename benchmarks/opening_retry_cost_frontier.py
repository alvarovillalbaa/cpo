"""Compare the retry cycle with native GEPA at the same realized cost."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import opening_residual_retry as retry
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.paid_budget_frontier import best_subject_allocation
from cpo._contract import digest
from cpo.family_qualification import certify_family_qualification


REFERENCE = '0cd73511836db8a5ee2dccace2c8222d94a9e1eecf1a3ac2b8b9906f34eee5f9'
CAPS = (32, 40, 48, 56, 64, 80, 96, 112, 128)
SOURCE = retry.SOURCE
TYPED = SOURCE.typed


def prepare():
    upstream, cohorts, _ = retry.prepare()
    frozen = checked_file('docs/opening-residual-retry-results-v1.json', REFERENCE)
    if digest(upstream) != frozen['designSha256']:
        raise ValueError('The sealed retry confirmation changed')
    design = {'protocol': 'cpo-opening-retry-cost-frontier-v1', 'gepaVersion': upstream['gepaVersion'],
              'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'confirmationDesignSha256': digest(upstream),
              'allocationSourceSha256': sha256(Path(__file__).with_name('paid_budget_frontier.py').read_bytes()).hexdigest(),
              'referenceReportSha256': REFERENCE, 'referenceCpoCap': upstream['searchCap'], 'gepaCaps': CAPS,
              'scope': ('Reuse the scripted confirmation panels. Compare a fixed native GEPA setting and a hindsight '
                        'per-panel allocation at the actual CPO call cost, including qualification and proposal calls.')}
    return design, cohorts['confirmation'], frozen['results']['phases']['confirmation']


def point(arm):
    return {'holdoutPasses': sum(arm['holdout'].values()),
            'countedCalls': sum(arm[key] for key in ('searchLookups', 'qualificationLookups', 'proposalCalls'))}


def sweep(task, profile, seed, groups):
    reference = retry.compare(task, profile, seed, groups)['arms']
    points = {}
    with (patch.object(TYPED, 'ARMS', TYPED.GEPA),
          patch.object(TYPED, 'certify_paired_qualification', certify_family_qualification),
          patch.object(TYPED, 'FAMILY_FIELD', {key: value[0][0] for key, value in SOURCE.TASKS.items()}),
          patch.object(TYPED.fixture, 'respond', lambda request: SOURCE.opening(profile, request)),
          patch.object(TYPED.programs, 'complete', SOURCE.complete), patch.object(TYPED.feedback, 'observed_repair', SOURCE.repair)):
        for cap in CAPS:
            arms = TYPED.trial(task, groups, seed, cap)['arms']
            if cap == SOURCE.CAP and any(result != reference[arm] for arm, result in arms.items()):
                raise ValueError('The native GEPA trace at the original cap changed')
            for arm, result in arms.items():
                points[arm, cap] = point(result)
    return {'points': points, 'cpo': point(reference[retry.PRIMARY]), 'retain': point(reference['retain-start'])}


def summarize(panels):
    totals = {}
    menu = {}
    cpo = Counter()
    for name, record in panels.items():
        cpo.update(record['cpo'])
        menu[name] = []
        for (method, cap), data in record['points'].items():
            totals.setdefault((method, cap), Counter()).update(data)
            menu[name].append({'method': method, 'cap': cap, 'holdoutPasses': data['holdoutPasses'],
                               'paidLookups': data['countedCalls']})
        start = record['retain']
        menu[name].append({'method': 'retain-start', 'cap': 0, 'holdoutPasses': start['holdoutPasses'],
                           'paidLookups': start['countedCalls']})
    fixed_points = [{'method': method, 'cap': cap, **data} for (method, cap), data in sorted(totals.items())]
    budget = cpo['countedCalls']
    affordable = [row for row in fixed_points if row['countedCalls'] <= budget]
    best = max(affordable, key=lambda row: (row['holdoutPasses'], -row['countedCalls']), default=None)
    score_matched = [row for row in fixed_points if row['holdoutPasses'] >= cpo['holdoutPasses']]
    cheapest = min(score_matched, key=lambda row: row['countedCalls'], default=None)
    oracle = best_subject_allocation(menu, budget)
    return {'cpo': dict(cpo), 'fixedGepaPoints': fixed_points, 'bestFixedGepaAtCpoCost': best,
            'cheapestFixedGepaAtCpoScore': cheapest,
            'perPanelGepaHindsightAtCpoCost': {'holdoutPasses': oracle['holdoutPasses'],
                                              'countedCalls': oracle['paidLookups'],
                                              'allocation': oracle['allocation']},
            'traceSha256': digest(menu)}


def measure(panels, frozen):
    modes = {'held-out': {}, 'shifted-exceptions': {}}
    for name, (original, alternate, shifted) in panels.items():
        task, profile, seed = name.split('/')
        modes['held-out'][name] = sweep(task, profile, int(seed), original)
        with patch.object(SOURCE, 'FAULTS', shifted):
            modes['shifted-exceptions'][name] = sweep(task, profile, int(seed), alternate)
    results = {mode: summarize(records) for mode, records in modes.items()}
    for mode, summary in results.items():
        expected = frozen[mode]['totals'][retry.PRIMARY]
        if any(summary['cpo'][key] != expected[key] for key in summary['cpo']):
            raise ValueError(f'The paid CPO reference changed for {mode}')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    design, panels, frozen = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Supply the current seal and a fresh output path')
    if version('gepa') != design['gepaVersion']:
        parser.error('Use GEPA 0.1.4')
    result = measure(panels, frozen)
    with args.out.open('x') as output:
        json.dump({'design': design, 'designSha256': seal, 'results': result}, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
