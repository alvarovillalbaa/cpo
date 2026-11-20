"""Transfer the witnessed validation-tie rule to the ARC-AGI and AIME archives."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import routed_validation_ties as ties
from benchmarks.four_case_qualification_transfer import interval
from cpo import Observation, Row, select_pool
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'benchmarks/data/gepa-recorded-math-v1.json'
CORPUS_SHA = '83ea1db450d2113b23066158e8f4d6b6ba02b7dd537f9ae557ab41f331565e1f'
SOURCE_REPORT_SHA = '783dafd77b24c294b4f63581be795a731331ce824b53af5a3508bbc60fc20c07'
DATASETS = {'arc': {'cohorts': (18, 8, 6, 48), 'seeds': tuple(range(16141, 16901, 19))},
            'aime': {'cohorts': (10, 6, 4, 25), 'seeds': tuple(range(17011, 17771, 19))}}
POLICIES = {'strict': None, 'paid-tie': 0, 'finish-four': 4}
GEPA = {'gepa-sequential': False, 'gepa-batched': True}
METHODS = (*POLICIES, *GEPA, 'retain-start')
CANDIDATE = 'finish-four'
BOUND = 180


def prepare():
    raw = CORPUS.read_bytes()
    previous = (ROOT / 'docs/routed-validation-ties-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != CORPUS_SHA or sha256(previous).hexdigest() != SOURCE_REPORT_SHA:
        raise ValueError('The archived pools or tie experiment differ from the frozen sources')
    paths = ('benchmarks/recorded_math_validation_ties.py', 'benchmarks/routed_validation_ties.py',
             'benchmarks/gepa_paid_cap_transfer.py', 'cpo/pool.py', 'cpo/paired_qualification.py')
    plan = {'protocol': 'cpo-recorded-math-validation-ties-v1', 'corpusSha256': CORPUS_SHA,
            'priorReportSha256': SOURCE_REPORT_SHA, 'gepaVersion': '0.1.4',
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'datasets': DATASETS, 'challengerCounts': (4, 8), 'incumbentGroups': ('root', 'rotated'),
            'searchCap': BOUND, 'methods': METHODS, 'candidate': CANDIDATE, 'primaryControls': tuple(GEPA),
            'bootstrapSeed': 20261126, 'bootstrapDraws': 4096, 'minimumLookupSavingPercent': 10,
            'scope': ('Keep the archived split seeds and holdout, reserve disjoint qualification cases, '
                      'and give every arm a shared roster. Transfer the witnessed tie fallback to a strict '
                      'fixed-pool race. Audit strict CPO under the same gate and omit each rotated start '
                      'in turn. Report ARC historical costs and AIME lookup counts.')}
    return plan, json.loads(raw)


def split_cases(size, seed, sizes):
    cases = list(range(size))
    Random(seed).shuffle(cases)
    training, validation, qualification, holdout = sizes
    a, b, c = training, training + validation, training + validation + qualification
    if c + holdout != size:
        raise ValueError('The four case sets must partition the archive')
    return cases[:a], cases[a:b], cases[b:c], cases[c:]


def load_cells(name, record):
    if name == 'arc':
        data = {}
        for candidate in record['candidates']:
            rows = tuple(candidate['rows'])
            if len(rows) != len(record['cases']) or sum(row[0] for row in rows) != candidate['sourceSolved']:
                raise ValueError('The ARC source solved counts must match each complete case vector')
            data[str(candidate['id'])] = rows
        return data
    return {str(candidate['id']): tuple((int(passed), None, False) for passed in candidate['passed'])
            for candidate in record['candidates']}


def select(incumbent, roster, rows, observe, journal, *, method, cap):
    result = select_pool((incumbent, *roster), rows, observe, metric_limit=cap, adaptive_rejection=True)
    if result.evaluations != len(journal):
        raise ValueError('Search ledger differs from the strict fixed-pool selector')
    extra = POLICIES[method]
    if result.prompt != incumbent or extra is None:
        return result.prompt, False
    tied = ties.certified_tie(incumbent, roster, rows, journal, observe, extra=extra, metric_limit=cap)
    return tied or incumbent, tied is not None


def run_trial(cells, incumbent, roster, cohorts, seed, method, cap):
    train, validation, qualification, held = cohorts
    search_cases = set(train + validation)
    qualification_cases = set(qualification)
    allowed = {incumbent, *roster}
    search, confirm = {}, {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if prompt not in allowed or int(row.id) not in search_cases:
            raise ValueError('Search left the shared prompt or case roster')
        if key not in search:
            if len(search) == cap:
                raise ValueError('Search exceeded the common ceiling')
            search[key] = Observation(bool(cells[prompt][int(row.id)][0]), {})
        return search[key]

    def qualify(prompt, row, repeat):
        case = int(row.id)
        key = (prompt, row.id)
        if repeat or prompt not in allowed or case not in qualification_cases or key in confirm:
            raise ValueError('Qualification left the distinct reserved cases or repeated a paid reply')
        confirm[key] = bool(cells[prompt][case][0])
        return confirm[key]

    tied = False
    if method in GEPA:
        nominee, _ = gepa.optimize_by_paid_reads(
            incumbent, roster, train, validation, lambda p, c: observe(p, Row(str(c), 'case')).passed,
            lambda: len(search), paid_limit=cap, batched=GEPA[method], seed=seed)
    elif method == 'retain-start':
        nominee = incumbent
    else:
        rows = tuple(Row(str(case), 'validation') for case in validation)
        nominee, tied = select(incumbent, roster, rows, observe, search, method=method, cap=cap)
    rows = tuple(Row(str(case), 'qualification') for case in qualification)
    result = certify_paired_qualification(incumbent, nominee, rows, qualify, seed=seed)
    passed = tuple(int(cells[result.prompt][case][0]) for case in held)
    metrics = {'holdoutPasses': sum(passed), 'searchLookups': len(search), 'qualificationLookups': len(confirm),
               'paidLookups': len(search) + len(confirm), 'tieNominations': int(tied),
               'tiePromotions': int(tied and result.status == 'promoted')}
    if cells[incumbent][0][1] is not None:
        keys = (*search, *confirm)
        metrics['historicalCostNanodollars'] = sum(cells[prompt][int(case)][1] for prompt, case in keys)
        metrics['historicalErrors'] = sum(cells[prompt][int(case)][2] for prompt, case in keys)
    return metrics, (seed, incumbent, nominee, result.prompt, digest([list(search), list(confirm)])), passed


def paired_ranges(vectors, candidate, controls, plan):
    rng = Random(plan['bootstrapSeed'])
    samples = {label: [] for label in (*controls, 'joint')}
    for _ in range(plan['bootstrapDraws']):
        size = len(vectors[candidate])
        sampled = rng.choices(range(size), k=size)
        margins = {label: sum(vectors[candidate][case] - vectors[label][case] for case in sampled)
                   for label in controls}
        margins['joint'] = min(margins[label] for label in GEPA)
        for label, values in samples.items():
            values.append(margins[label])
    return {label: interval(values) for label, values in samples.items()}


def comparison(candidate, totals, ranges, plan):
    primary = totals[candidate]
    savings = {label: (totals[label]['paidLookups'] - primary['paidLookups']) / totals[label]['paidLookups']
               for label in GEPA}
    saves_enough = all(100 * primary['paidLookups'] <= (100 - plan['minimumLookupSavingPercent']) * totals[label]['paidLookups']
                       for label in GEPA)
    historical = primary.get('historicalCostNanodollars')
    low, high = ranges['joint']
    if (high < 0 or not saves_enough
            or historical is not None and any(historical > totals[label]['historicalCostNanodollars'] for label in GEPA)):
        gate = 'failed'
    else:
        gate = 'passed' if low >= 0 else 'inconclusive'
    return {'caseSensitivityRanges': ranges, 'lookupSavingFractions': savings, 'gate': gate}


def measure_group(cells, settings, group, width, plan):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals = {label: Counter() for label in METHODS}
    by_start = {start: {label: Counter() for label in METHODS} for start in starts}
    receipts = {label: [] for label in METHODS}
    vectors = {label: [0] * size for label in METHODS}
    changed = {label: Counter() for label in POLICIES if label != 'strict'}
    for seed in settings['seeds']:
        cohorts = split_cases(size, seed, settings['cohorts'])
        held = cohorts[-1]
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            for label in METHODS:
                point, trace, passed = run_trial(cells, start, roster, cohorts, seed, label, plan['searchCap'])
                receipts[label].append(trace)
                totals[label].update(point)
                by_start[start][label].update(point)
                for case, outcome in zip(held, passed, strict=True):
                    vectors[label][case] += outcome
                if label == 'strict':
                    strict = point['holdoutPasses']
                if label in changed:
                    diff = point['holdoutPasses'] - strict
                    changed[label].update(episodesGaining=int(diff > 0), episodesLosing=int(diff < 0),
                                          grossGain=max(0, diff), grossLoss=max(0, -diff))
    if any(sum(vectors[label]) != point['holdoutPasses'] for label, point in totals.items()):
        raise ValueError('Paired case totals must reproduce the trial results')
    ranges = paired_ranges(vectors, CANDIDATE, ('strict', *GEPA), plan)
    strict_ranges = paired_ranges(vectors, 'strict', GEPA, plan)
    return {'totals': {label: {**point, 'traceSha256': digest(receipts[label])} for label, point in totals.items()},
            'trialsPerMethod': len(starts) * len(settings['seeds']), 'changesFromStrict': changed,
            **comparison(CANDIDATE, totals, ranges, plan),
            'strictComparison': comparison('strict', totals, strict_ranges, plan), 'byStart': by_start}


def replay(plan, sources):
    results = {}
    for name, settings in plan['datasets'].items():
        cells = load_cells(name, sources[name]['record'])
        results[name] = {f'{group}/{width}': measure_group(cells, settings, group, width, plan)
                         for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, sources = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, sources)
    with args.out.open('x') as out:
        json.dump(report, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
