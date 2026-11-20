"""Let stronger independent qualification substitute for reserved training support."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_math_validation_ties as math
from benchmarks import recorded_training_backup as backup
from benchmarks import recorded_training_corroboration as training
from benchmarks import recorded_validation_stability as prior
from cpo import Row
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
PARENT_SHA256 = 'e28e02dd61f2a53ca927c5a389774647bad110b8d4b8c5074667cd96e99d0fbb'
CONTROLS = ('retain-start', 'strict-precheck', 'certified-precheck', *prior.QUALIFICATION_PRECHECK.values())
POLICIES = ('training-only', 'strength-only', 'strength-first', 'training-first')
METHODS = (*CONTROLS, *POLICIES)


def qualify_with_support(incumbent, challenger, rows, evaluate, corroborate, *, seed, policy, audit):
    """Certify a gain of one and require either a second gain or training support."""
    seen = {}

    def read(prompt, row, repeat):
        key = (prompt, row.id, repeat)
        if key not in seen:
            seen[key] = evaluate(prompt, row, repeat)
        return seen[key]

    decision = certify_paired_qualification(incumbent, challenger, rows, read, seed=seed)
    if decision.status != 'promoted':
        return decision
    audit.update(initialPromotions=1)

    def strong():
        nonlocal decision
        if decision.upper_gain < 2:
            return False
        before = len(seen)
        decision = certify_paired_qualification(incumbent, challenger, rows, read, seed=seed, minimum_gain=2)
        supported = decision.status == 'promoted'
        audit.update(strengthChecks=1, readForStrength=len(seen) - before, strengthProved=int(supported))
        return supported

    if policy == 'training-only':
        supported = corroborate()
    elif policy == 'strength-only':
        supported = strong()
    elif policy == 'strength-first':
        supported = strong() or corroborate()
    else:
        supported = corroborate() or strong()
    audit.update(promotions=int(supported))
    return replace(decision, status='promoted' if supported else 'rejected',
                   prompt=challenger if supported else incumbent)


def run_trial(cells, start, roster, cohorts, seed, method, cap):
    if method in CONTROLS:
        return prior.run_trial(cells, start, roster, cohorts, seed, method, cap)

    original = math.select
    state, audit = {}, Counter()

    def select(incumbent, candidates, rows, observe, journal, *, method, cap):
        state.update(observe=observe, journal=journal)
        return original(incumbent, candidates, rows, observe, journal, method=method, cap=cap)

    def qualify(incumbent, challenger, rows, evaluate, *, seed):
        def corroborate():
            panel = tuple(Row(str(case), 'training') for case in cohorts[0][:len(cohorts[0]) // 2])
            before = len(state['journal'])
            supported = training.corroborate(incumbent, challenger, panel, state['observe'], minimum_gain=1,
                                              remaining=cap - before, seed=seed)
            audit.update(trainingChecks=1, trainingProved=int(supported),
                         paidTrainingLookups=len(state['journal']) - before)
            return supported

        return qualify_with_support(incumbent, challenger, rows, evaluate, corroborate,
                                    seed=seed, policy=method, audit=audit)

    with (patch.object(math, 'select', select),
          patch.object(math, 'certify_paired_qualification', qualify),
          patch.dict(backup.PRECHECKED, {'strict-precheck': 'strict'})):
        totals, trace, passed = backup.run_prechecked(cells, start, roster, cohorts, seed, 'strict-precheck', cap)
    return {**totals, **audit}, trace, passed


def prepare():
    parent, data, _ = prior.prepare()
    raw = (ROOT / 'docs/recorded-validation-stability-results-v1.json').read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('The published matched controls do not match their seal')
    paths = ('benchmarks/recorded_margin_corroboration.py', *parent['sourceSha256'])
    plan = {**{key: parent[key] for key in ('gepaVersion', 'datasets', 'challengerCounts', 'incumbentGroups', 'searchCap',
                                           'bootstrapSeed', 'bootstrapDraws', 'minimumLookupSavingPercent')},
            'protocol': 'cpo-recorded-margin-corroboration-v1', 'methods': METHODS,
            'parentPlanSha256': digest(parent), 'parentReportSha256': PARENT_SHA256,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'rule': 'After proving a qualification gain of one, prove a gain of two or a first-half training gain.'}
    return plan, data, reference['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals, traces = {method: Counter() for method in METHODS}, {method: [] for method in METHODS}
    vectors = {method: [0] * size for method in METHODS}
    paired = 0
    for seed in settings['seeds']:
        cohorts = math.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            ordered = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(ordered, len(ordered))[:width]
            for method in METHODS:
                point, trace, passed = run_trial(cells, start, roster, cohorts, seed, method, plan['searchCap'])
                totals[method].update(point)
                traces[method].append(trace)
                for case, outcome in zip(cohorts[-1], passed, strict=True):
                    vectors[method][case] += outcome
            if traces['training-first'][-1][:4] != traces['strength-first'][-1][:4]:
                raise ValueError('The order of the last two proofs changed deployment')
            _, original, _ = training.run_trial(cells, start, roster, cohorts, seed,
                                                'half-training-support', plan['searchCap'])
            if original[3] != traces['training-only'][-1][3]:
                raise ValueError('The incumbent precheck changed the original training-only decision')
            paired += 1
    points = {method: {**total, 'traceSha256': digest(traces[method])} for method, total in totals.items()}
    if any(points[arm] != reference['totals'][arm] for arm in CONTROLS):
        raise ValueError('A matched control no longer reproduces its recorded metrics and trace')
    if any(sum(vector) != totals[arm]['holdoutPasses'] for arm, vector in vectors.items()):
        raise ValueError('The paired vectors do not account for all held-out scores')

    matched_totals = {**totals, **{rival: totals[arm] for rival, arm in prior.QUALIFICATION_PRECHECK.items()}}
    matched_vectors = {**vectors, **{rival: vectors[arm] for rival, arm in prior.QUALIFICATION_PRECHECK.items()}}
    controls = ('training-only', 'strict-precheck', *math.GEPA)
    comparisons = {arm: math.comparison(arm, matched_totals, math.paired_ranges(matched_vectors, arm, controls, plan), plan)
                   for arm in POLICIES}
    return {'totals': points, 'comparisons': comparisons, 'decisionsMatchedAcrossProofOrders': paired,
            'trainingOnlyDecisionsMatched': paired}


def replay(plan, sources, reference):
    results = {}
    for domain, settings in plan['datasets'].items():
        cells = math.load_cells(domain, sources[domain]['record'])
        results[domain] = {f'{group}/{width}': measure(cells, settings, group, width, plan, reference[domain][f'{group}/{width}'])
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
