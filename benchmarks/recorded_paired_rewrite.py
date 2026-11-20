"""Measure exact paid-read savings for supplied rewrites against native GEPA."""

import argparse
from collections import Counter
from functools import cache
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_opening_dominance_transfer as transfer
from cpo import Observation, Row
from cpo._contract import digest
from cpo.paired_rewrite import select_same_parent_rewrites


REFERENCE = transfer.ROOT / 'docs/recorded-opening-dominance-transfer-results-v1.json'
REFERENCE_SHA = 'd55d3dccc80b27ec2058e66c54924bfbd61af31c2383955e4d600edc7a1eb24e'
PAIRED_REFERENCE = transfer.ROOT / 'docs/recorded-paired-rewrite-results-v1.json'
PAIRED_REFERENCE_SHA = '93a4961939b6e6dbdba1a9633d888e65a8721ffe13bb09482aa71e9fa1abc00c'
NATIVE = 'gepa-rewrite'
BATCHED = 'gepa-batched'


def prepare():
    prior, scores = transfer.prepare()
    raw = REFERENCE.read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or reference['planSha256'] != digest(prior):
        raise ValueError('The fixed-opening control differs from the published replay')
    names = ('benchmarks/recorded_paired_rewrite.py', 'cpo/paired_rewrite.py')
    plan = {'protocol': 'recorded-paired-rewrite-v1', 'parentPlanSha256': digest(prior),
            'referenceSha256': REFERENCE_SHA, 'gepaVersion': '0.1.4', 'datasets': prior['datasets'],
            'incumbentGroups': prior['incumbentGroups'], 'nativeControl': NATIVE,
            'sourcesSha256': {name: sha256((transfer.ROOT / name).read_bytes()).hexdigest() for name in names},
            'scope': 'native first minibatch, strict binary gains, unchanged independent admission'}
    return plan, scores, reference['results']


def compare_group(cells, settings, starts, reference, *, charge_aware=False, control=NATIVE):
    native_select = transfer.gepa_cached_opening.select_opening

    @cache
    def minibatches(size, seed, count):
        """Discover the seeded same-parent minibatches with synthetic replies."""
        rows = [{'id': str(index), 'expected': {'pass': True}} for index in range(size)]
        prompts = tuple(f'rewrite-{index}' for index in range(count))
        observed = {prompt: [] for prompt in prompts}

        def evaluate(prompt, case):
            if prompt in observed:
                observed[prompt].append(int(case))
            return Observation(False, {}, 0)

        selected = native_select('incumbent', prompts, {'validation': rows}, evaluate,
                                 cap=(1 + count) * size, seed=seed, width=count, minibatch_size=2)
        if selected != 'incumbent' or any(len(set(batch)) != 2 or len(batch) != 2 for batch in observed.values()):
            raise ValueError('The synthetic probe did not recover the native minibatches')
        return tuple(tuple(batch) for batch in observed.values())

    totals = {'native': Counter(), 'paired': Counter()}
    traces = {'native': [], 'paired': []}
    savings = Counter(pathsWithFewerReads=0, pathsWithLowerCost=0)
    size = len(next(iter(cells.values())))
    for seed in settings['seeds']:
        cohorts = transfer.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            others = [prompt for prompt in cells if prompt != start]
            pair = Random(f'{seed}/{start}').sample(others, len(others))[:2]
            observed = {'native': set(), 'paired': set()}

            def run(mode):
                def select(incumbent, bank, groups, evaluate, *, cap, seed, width, minibatch_size):
                    def read(prompt, case):
                        observed[mode].add((prompt, case))
                        return evaluate(prompt, case)

                    if mode == 'native':
                        return native_select(incumbent, bank, groups, read, cap=cap, seed=seed, width=width,
                                             minibatch_size=minibatch_size)
                    validation = tuple(Row(row['id'], 'archive') for row in groups['validation'])
                    batches = minibatches(len(validation), seed, len(bank))
                    proposals = tuple((prompt, tuple(validation[index].id for index in batch))
                                      for prompt, batch in zip(bank, batches, strict=True))

                    def observed_charge(prompt, row, _reply):
                        return cells[prompt][int(row.id)][1]

                    charge = observed_charge if charge_aware else None
                    return select_same_parent_rewrites(incumbent, proposals, validation,
                                                       lambda prompt, row: read(prompt, row.id),
                                                       observed_charge=charge)

                with patch.object(transfer.gepa_cached_opening, 'select_opening', select):
                    point = transfer.trial(cells, start, pair, cohorts, seed, control)
                traces[mode].append([seed, start, pair, point])
                totals[mode].update(point['totals'])
                return point

            native, paired = run('native'), run('paired')
            if any(native[key] != paired[key] for key in ('nominee', 'selected', 'admission', 'passed')):
                raise ValueError('Paired bounds changed a native decision')
            if not observed['paired'] <= observed['native']:
                raise ValueError('Paired bounds paid for a new case outside the native path')
            old, new = native['totals'], paired['totals']
            savings['pathsWithFewerReads'] += new['paidReads'] < old['paidReads']
            if 'historicalCostNanodollars' in old:
                savings['pathsWithLowerCost'] += new['historicalCostNanodollars'] < old['historicalCostNanodollars']
    points = {mode: {**record, 'traceSha256': digest(traces[mode])} for mode, record in totals.items()}
    if points['native'] != reference['totals'][control]:
        raise ValueError('The native control did not reproduce its complete published trace')
    return {'pathsPerArm': len(traces['native']), 'heldoutUsesPerArm': reference['heldoutUsesPerArm'],
            'totals': points, 'savings': savings}


def measure(plan, sources, reference):
    results = {}
    for task, settings in plan['datasets'].items():
        cells = transfer.load_cells(task, sources[task]['record'])
        starts = tuple(cells)
        results[task] = {name: compare_group(cells, settings, starts[:1] if name == 'root' else starts[1:],
                                             reference[task][name]) for name in plan['incumbentGroups']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def archived_controls():
    prior, sources = transfer.prepare()
    native, paired = REFERENCE.read_bytes(), PAIRED_REFERENCE.read_bytes()
    if sha256(native).hexdigest() != REFERENCE_SHA or sha256(paired).hexdigest() != PAIRED_REFERENCE_SHA:
        raise ValueError('A published comparison receipt differs from its recorded hash')
    expected = json.loads(native)['results']
    baseline = json.loads(paired)
    if digest(baseline['plan']['datasets']) != digest(prior['datasets']):
        raise ValueError('Charge-aware ordering must use the original comparison cohorts')
    return prior, sources, expected, baseline


def measure_charge_aware():
    prior, sources, expected, baseline = archived_controls()
    results = {}
    for task, settings in prior['datasets'].items():
        cells = transfer.load_cells(task, sources[task]['record'])
        starts = tuple(cells)
        results[task] = {}
        for group in prior['incumbentGroups']:
            incumbents = starts[:1] if group == 'root' else starts[1:]
            before = compare_group(cells, settings, incumbents, expected[task][group])
            if before != baseline['results'][task][group]:
                raise ValueError('The row-paired read trace differs from its published baseline')
            after = compare_group(cells, settings, incumbents, expected[task][group], charge_aware=True)
            results[task][group] = {'paths': after['pathsPerArm'], 'heldoutUses': after['heldoutUsesPerArm'],
                                    'native': before['totals']['native'], 'rowPaired': before['totals']['paired'],
                                    'chargeAware': after['totals']['paired']}
    return {'schema': 'recorded-binary-charge-aware-rewrite-v1', 'pairedReferenceSha256': PAIRED_REFERENCE_SHA,
            'corpusSha256': prior['corpusSha256'], 'newProviderRequests': 0, 'results': results}


def measure_same_parent_charge_aware():
    prior, sources, expected, _ = archived_controls()
    results = {}
    for task, settings in prior['datasets'].items():
        cells = transfer.load_cells(task, sources[task]['record'])
        starts = tuple(cells)
        results[task] = {}
        for group in prior['incumbentGroups']:
            incumbents = starts[:1] if group == 'root' else starts[1:]
            before = compare_group(cells, settings, incumbents, expected[task][group], control=BATCHED)
            after = compare_group(cells, settings, incumbents, expected[task][group], control=BATCHED, charge_aware=True)
            results[task][group] = {'paths': after['pathsPerArm'], 'heldoutUses': after['heldoutUsesPerArm'],
                                    'native': before['totals']['native'], 'rowPaired': before['totals']['paired'],
                                    'chargeAware': after['totals']['paired'], 'chargeAwareSavings': after['savings']}
    return {'schema': 'recorded-same-parent-charge-aware-rewrite-v1', 'nativeReferenceSha256': REFERENCE_SHA,
            'corpusSha256': prior['corpusSha256'], 'newProviderRequests': 0, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', metavar='PLAN_SHA256')
    mode.add_argument('--charge-aware', action='store_true', help='Replay the observed-charge policy offline')
    mode.add_argument('--same-parent-charge-aware', action='store_true', help='Replay both supplied rewrites offline')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.charge_aware or args.same_parent_charge_aware:
        if args.out is not None or version('gepa') != '0.1.4':
            parser.error('Use GEPA 0.1.4 and capture the charge-aware report from stdout')
        measure_offline = measure_charge_aware if args.charge_aware else measure_same_parent_charge_aware
        print(json.dumps(measure_offline(), indent=2, sort_keys=True))
        return
    plan, sources, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Use the current seal, GEPA 0.1.4, and a fresh output path')
    report = measure(plan, sources, reference)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
