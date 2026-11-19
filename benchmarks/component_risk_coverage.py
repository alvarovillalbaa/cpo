"""Measure whether validation coverage prevents critical component regressions."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import component_dependencies as prior
from benchmarks.frontier import FAMILIES
from cpo import Row
from cpo._contract import digest
from cpo.validation import sample_validation_panel


SEEDS = tuple(range(65601, 66209, 19))
PANELS = ('original', 'matched', 'stratified', 'six-critical')
SEARCHES = ('cpo-dependencies', 'gepa-dependencies', 'gepa-dependencies-merge')
ARMS = tuple(f'{method}.{panel}' for panel in PANELS for method in SEARCHES)
PRIMARY = 'cpo-dependencies.stratified'
REFERENCE = 'gepa-dependencies.original'
DONORS = 6
PROGRAMS = tuple(dict(zip(FAMILIES, states)) for states in product(('off', 'guarded', 'broad'), repeat=len(FAMILIES)))


def risk_stratum(row):
    # The fixture exposes the operation family and whether the case has legacy or interaction risk.
    return f"{row['family']}:{'interaction' if row['needs'] else 'legacy'}"


def make_panels(profile, seed):
    groups = prior.cases(profile, seed)
    original = groups['validation']
    pool = list(original)
    for index in range(DONORS):
        extra = prior.cases(profile, seed + 70_000 * (index + 1))['validation']
        pool.extend({**row, 'id': f'{seed}-validation-pool-{index}-{slot}'} for slot, row in enumerate(extra))
    source = {row['id']: row for row in pool}
    rows = [Row(case, row['family'], row['critical']) for case, row in source.items()]
    labels = {case: risk_stratum(row) for case, row in source.items() if row['critical']}
    quota = sum(row['critical'] for row in original)
    panels = {'original': groups}
    for mode, count, strata in (('matched', quota, None), ('stratified', quota, labels), ('six-critical', 6, labels)):
        selected = sample_validation_panel(rows, size=len(original), critical_count=count, critical_strata=strata, seed=seed)
        panels[mode] = {**groups, 'validation': [source[row.id] for row in selected]}
    return panels


def attainable_gain(profile, holdout, benchmark):
    """After selection, enumerate the fixture language to bound potential improvement."""
    protected = {row['id'] for row in holdout if row['critical'] and benchmark[row['id']]}
    ceiling = 0
    for program in PROGRAMS:
        passed = {row['id'] for row in holdout if prior.score(program, row, profile).passed}
        if protected <= passed:
            ceiling = max(ceiling, len(passed))
    return ceiling - sum(benchmark.values())


def compare(profile, seed, cap):
    panels = make_panels(profile, seed)
    arms, coverage = {}, {}
    for mode, groups in panels.items():
        with patch.object(prior, 'ARMS', SEARCHES), patch.object(prior, 'cases', return_value=groups):
            result = prior.compare(profile, seed, cap)
        validation = groups['validation']
        arms.update({f'{arm}.{mode}': value for arm, value in result['arms'].items()})
        coverage[mode] = {'criticalRows': sum(row['critical'] for row in validation),
                          'strata': sorted({risk_stratum(row) for row in validation if row['critical']})}

    holdout = panels['original']['holdout']
    reference = arms[REFERENCE]['outcomes']
    losses = {}
    for mode in PANELS:
        outcome = arms[f'cpo-dependencies.{mode}']['outcomes']
        losses[mode] = {'represented': 0, 'missing': 0}
        for row in holdout:
            if row['critical'] and reference[row['id']] and not outcome[row['id']]:
                represented = risk_stratum(row) in coverage[mode]['strata']
                losses[mode]['represented' if represented else 'missing'] += 1
    return {'seed': seed, 'arms': arms, 'critical': result['critical'], 'coverage': coverage, 'losses': losses,
            'attainableGain': attainable_gain(profile, holdout, reference)}


def summarize(trials):
    with patch.object(prior, 'ARMS', ARMS), patch.object(prior, 'PRIMARY', PRIMARY):
        summary = prior.summarize(trials)
    coverage = {}
    for mode in PANELS:
        losses = Counter()
        for trial in trials:
            losses.update(trial['losses'][mode])
        coverage[mode] = {'criticalRows': sum(trial['coverage'][mode]['criticalRows'] for trial in trials),
                          'distinctStrata': sum(len(trial['coverage'][mode]['strata']) for trial in trials),
                          'lossesAgainstOriginalGepa': dict(losses)}
    return {**summary, 'coverage': coverage, 'gepaAtQualityCeiling': sum(trial['attainableGain'] == 0 for trial in trials),
            'maximumGainAtEqualCriticalCoverage': sum(trial['attainableGain'] for trial in trials), 'trials': trials}


def prepare():
    plan = prior.prepare()
    root = Path(__file__).resolve().parents[1]
    for name in ('benchmarks/component_risk_coverage.py', 'cpo/validation.py'):
        plan['sourceSha256'][name] = sha256((root / name).read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-component-risk-coverage-v1', 'seeds': list(SEEDS), 'arms': list(ARMS),
            'primary': PRIMARY, 'panels': list(PANELS), 'donorPanels': DONORS,
            'cohortDigests': {profile: digest([make_panels(profile, seed) for seed in SEEDS]) for profile in prior.PROFILES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {}
    for cap in plan['caps']:
        results[str(cap)] = {}
        for profile in plan['profiles']:
            trials = [compare(profile, seed, cap) for seed in plan['seeds']]
            results[str(cap)][profile] = summarize(trials)
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
