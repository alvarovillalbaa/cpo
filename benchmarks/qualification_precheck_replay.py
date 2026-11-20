"""Replay matched CPO and GEPA qualification through the public precheck."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import recorded_math_validation_ties as math
from benchmarks import recorded_validation_stability as prior
from cpo import Observation, Row
from cpo._contract import digest
from cpo.qualification_precheck import run_prechecked_qualification


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = 'e28e02dd61f2a53ca927c5a389774647bad110b8d4b8c5074667cd96e99d0fbb'
METHODS = ('strict', *math.GEPA)


def prepare():
    parent, sources, _ = prior.prepare()
    raw = (ROOT / 'docs/recorded-validation-stability-results-v1.json').read_bytes()
    expected = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or expected['planSha256'] != digest(parent):
        raise ValueError('The matched precheck comparison differs from the published evidence')
    paths = ('benchmarks/qualification_precheck_replay.py', 'benchmarks/gepa_paid_cap_transfer.py',
             'cpo/qualification_precheck.py', *parent['sourceSha256'])
    plan = {**{key: parent[key] for key in ('gepaVersion', 'datasets', 'challengerCounts', 'incumbentGroups', 'searchCap')},
            'protocol': 'cpo-qualification-precheck-replay-v1', 'parentPlanSha256': digest(parent),
            'parentReportSha256': PARENT_SHA256, 'methods': METHODS,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return plan, sources, expected['results']


def run_trial(cells, incumbent, roster, cohorts, seed, method, cap):
    train, validation, qualification, held = cohorts
    search_cases = set(train + validation)
    prompt_pool = {incumbent, *roster}
    qualifier, search = {}, {}

    def observe(prompt, row):
        key = (prompt, row.id)
        case = int(row.id)
        if prompt not in prompt_pool or case not in search_cases:
            raise ValueError('Search accessed an out-of-scope prompt or case')
        if key not in search:
            if len(search) == cap:
                raise ValueError('Search exceeded the paid limit')
            search[key] = Observation(bool(cells[prompt][case][0]), {})
        return search[key]

    def nominate():
        if method in math.GEPA:
            nominee, _ = math.gepa.optimize_by_paid_reads(
                incumbent, roster, train, validation, lambda p, c: observe(p, Row(str(c), 'case')).passed,
                lambda: len(search), paid_limit=cap, batched=math.GEPA[method], seed=seed,
            )
            return nominee
        rows = tuple(Row(str(case), 'validation') for case in validation)
        nominee, _ = math.select(incumbent, roster, rows, observe, search, method='strict', cap=cap)
        return nominee

    def qualify(prompt, row, repeat):
        key = (prompt, row.id)
        if repeat or prompt not in prompt_pool or int(row.id) not in qualification or key in qualifier:
            raise ValueError('A qualification request was duplicated or left its sealed scope')
        qualifier[key] = bool(cells[prompt][int(row.id)][0])
        return qualifier[key]

    rows = tuple(Row(str(case), 'qualification') for case in qualification)
    result = run_prechecked_qualification(incumbent, rows, nominate, qualify, seed=seed, evaluation_limit=2 * len(rows))
    observations = {(reply.prompt, reply.row_id): reply.passed for reply in result.decision.observations}
    if result.qualification_evaluations != len(qualifier) or list(observations.items()) != list(qualifier.items()):
        raise ValueError('The public result must account for every paid qualification callback in dispatch order')
    nominee = incumbent if result.nominee is None else result.nominee
    paid = list(qualifier)
    before = result.precheck_evaluations
    values = {'holdoutPasses': sum(cells[result.prompt][case][0] for case in held),
              'paidLookups': len(search) + len(paid), 'searchLookups': len(search), 'qualificationLookups': len(paid),
              'precheckLookups': before, 'precheckStops': int(result.nominee is None),
              'tieNominations': 0, 'tiePromotions': 0}
    if cells[incumbent][0][1] is not None:
        values['historicalCostNanodollars'] = sum(cells[prompt][int(case)][1] for prompt, case in (*search, *paid))
        values['historicalErrors'] = sum(cells[prompt][int(case)][2] for prompt, case in (*search, *paid))
    # Reconstruct the sealed receipt format, which has a separate precheck.
    precheck = [(int(case), qualifier[prompt, case]) for prompt, case in paid[:before]]
    signature = digest((precheck, digest([list(search), paid[before:]])))
    return values, (seed, incumbent, nominee, result.prompt, signature)


def measure(cells, settings, group, width, plan, reference):
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals = {method: Counter() for method in plan['methods']}
    traces = {method: [] for method in plan['methods']}
    size = len(next(iter(cells.values())))
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            for method in plan['methods']:
                point, trace = run_trial(cells, start, roster, cohorts, seed, method, plan['searchCap'])
                totals[method].update(point)
                traces[method].append(trace)
    results = {f'{method}-precheck': {**total, 'traceSha256': digest(traces[method])}
               for method, total in totals.items()}
    if results != {method: reference['totals'][method] for method in results}:
        raise ValueError('The public precheck did not reproduce the archived decisions or paid traces')
    return {'reproduced': results, 'trialsPerMethod': reference['trialsPerMethod']}


def replay(plan, sources, reference):
    results = {}
    for name, settings in plan['datasets'].items():
        cells = math.load_cells(name, sources[name]['record'])
        results[name] = {f'{group}/{width}': measure(cells, settings, group, width, plan, reference[name][f'{group}/{width}'])
                         for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, sources, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, sources, reference)
    with args.out.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
