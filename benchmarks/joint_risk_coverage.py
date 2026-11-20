"""Test risk coverage during joint instruction and demonstration selection."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import grounded_fixture, joint_sampler_comparison as parent, typed_policy
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
REPORT_SHA256 = 'd2c8de3def9d6e27ae7d3c6c2a230ffc85a92511d9ee98b849fba2cc4b66f308'
NEW_SEEDS = (43003, 43019, 43037, 43049, 43063, 43067)
METHODS = ('original', 'diverse-prefix', 'coverage-gate', 'combined', 'coverage-fallback', 'combined-fallback',
           'gepa-batched', 'gepa-sequential')
GEPA = METHODS[-2:]


def stratum(task, row):
    facts = grounded_fixture.facts(row['input'])
    if task == 'outage':
        return facts['Evidence'], 'long' if int(facts['Duration minutes']) >= 120 else 'short'
    if task == 'warehouse':
        return facts['Inspection'], facts['Tier']
    return (facts['Topic'],)


def critical_groups(task, validation):
    groups = defaultdict(list)
    for row in validation:
        if row['critical']:
            groups[stratum(task, row)].append(row)
    return groups


def diverse_prefix(task, validation, size):
    groups = critical_groups(task, validation)
    picked = set()
    visits = Counter()
    prefix = []
    for original in validation[:size]:
        if original['critical']:
            eligible = [key for key, rows in groups.items() if visits[key] < len(rows)]
            key = min(eligible, key=lambda group: (visits[group], len(groups[group]), group))
            row = groups[key][visits[key]]
            visits[key] += 1
        else:
            row = original
        picked.add(row['id'])
        prefix.append(row)
    return [*prefix, *(row for row in validation if row['id'] not in picked)]


def covers_strata(prompt, groups, journal):
    return all(any(journal[prompt, row['id']].passed for row in rows) for rows in groups.values())


def run_arm(task, cohorts, grid, seed, cap, method):
    if method in GEPA:
        return parent.run_arm(task, cohorts, grid, seed, cap, method)
    original_rows = cohorts['validation']
    diversified = method in ('diverse-prefix', 'combined', 'combined-fallback')
    rows = diverse_prefix(task, original_rows, parent.BATCH) if diversified else original_rows
    audit = Counter()
    groups = critical_groups(task, rows)
    original, sampler = parent.exact_gain, parent.sample_grid
    fallback = None

    def confirmation(prompt, validation, baseline, target, evaluate, journal, *, early):
        nonlocal fallback
        score = original(prompt, validation, baseline, target, evaluate, journal, early=early)
        if score is not None and not covers_strata(prompt, groups, journal):
            audit.update(coverageVetoes=1)
            if fallback is None or score > fallback[0]:
                fallback = (score, prompt)
            return None
        return score

    def sample(pool, *args, **kwargs):
        nominee, measured = sampler(pool, *args, **kwargs)
        if method.endswith('-fallback') and nominee == pool[0][0] and fallback is not None:
            audit.update(fallbackNominations=1)
            return fallback[1], measured
        return nominee, measured

    gate = confirmation if method in ('coverage-gate', 'combined', 'coverage-fallback', 'combined-fallback') else original
    with patch.object(parent, 'exact_gain', gate), patch.object(parent, 'sample_grid', sample):
        result = parent.run_arm(task, {**cohorts, 'validation': rows}, grid, seed, cap, 'tpe-cpo')
    return {**result, **audit}


def prepare():
    previous = parent.plan()
    raw = (ROOT / 'docs/joint-sampler-comparison-results-v1.json').read_bytes()
    archive = json.loads(raw)
    if sha256(raw).hexdigest() != REPORT_SHA256 or archive['planSha256'] != digest(previous):
        raise ValueError('Joint sampler results differ from the published seal')
    paths = ('benchmarks/joint_risk_coverage.py', *previous['sourceSha256'])
    cohorts = {'development': tuple(previous['seeds']), 'transfer': NEW_SEEDS}
    settings = {**{k: previous[k] for k in ('caps', 'gepaVersion', 'optunaVersion', 'minibatchSize')},
                'protocol': 'cpo-joint-risk-coverage-v1', 'methods': METHODS, 'cohorts': cohorts,
                'parentPlanSha256': digest(previous), 'parentReportSha256': REPORT_SHA256,
                'datasetSha256': {str(seed): digest(typed_policy.cohorts(seed))
                                  for seeds in cohorts.values() for seed in seeds},
                'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
                'primary': 'combined', 'scope': ('Keep minibatch size and critical quota fixed. Prefer distinct rare '
                                                'critical strata, or require one validated pass per stratum before '
                                                'nomination. Test allowing the best validated fallback if the gate '
                                                'offers no candidate. Keep independent qualification and GEPA controls.')}
    return settings, archive['panels']


def full_pool_support(task, cohorts, grid):
    """Count eligible programs after replay without looking at the holdout."""
    validation, training = cohorts['validation'], cohorts['train']

    def exact(program):
        return {row['id']: parent.grounded.score(
            parent.alt.complete(task, program, row['input'], training), row['expected'],
        )[0] for row in validation}

    baseline = exact(grid[0][0])
    protected = {row['id'] for row in validation if row['critical'] and baseline[row['id']]}
    groups = critical_groups(task, validation)
    count = 0
    for options in grid:
        for program in options:
            observed = exact(program)
            count += (sum(observed.values()) > sum(baseline.values())
                      and all(observed[key] for key in protected)
                      and all(any(observed[row['id']] for row in group) for group in groups.values()))
    return count


def summarize(seed_list, cap, expected):
    totals = {m: Counter() for m in METHODS}
    losses = {m: {control: Counter() for control in GEPA} for m in METHODS if m not in GEPA}
    panels, diagnostic = {}, Counter()
    for seed in seed_list:
        for task, cohorts in typed_policy.cohorts(seed).items():
            name = f'{seed}/{task}'
            grid = parent.candidate_grid(task, cohorts['train'], seed)
            rows = {m: run_arm(task, cohorts, grid, seed, cap, m) for m in METHODS}
            if not rows['combined']['promoted'] and rows['combined-fallback']['promoted']:
                supported = full_pool_support(task, cohorts, grid)
                diagnostic.update(fallbackRestoredPanels=1, noEligibleCandidateInFullPool=int(supported == 0))
            if expected is not None:
                for method in ('original', *GEPA):
                    original = 'tpe-cpo' if method == 'original' else method
                    if rows[method] != expected[name][original]:
                        raise ValueError('A development control differs from its published comparison')
            for method, point in rows.items():
                totals[method].update({k: v for k, v in point.items() if type(v) is int})
                if method in GEPA:
                    continue
                for control, counts in losses[method].items():
                    difference = point['holdoutPasses'] - rows[control]['holdoutPasses']
                    counts.update(holdoutDelta=difference, lookupDelta=point['paidLookups'] - rows[control]['paidLookups'])
                    for case in cohorts['holdout']:
                        if case['critical'] and rows[control]['holdout'][case['id']] and not point['holdout'][case['id']]:
                            counts.update(matchedCriticalLosses=1)
                            counts.update({f'{task}/' + '/'.join(stratum(task, case)): 1})
            panels[name] = rows
    return {'totals': totals, 'comparisons': losses, 'panels': panels, 'fullPoolDiagnostic': diagnostic}


def replay(settings, reference):
    results = {name: {str(cap): summarize(seeds, cap, reference[str(cap)] if name == 'development' else None)
                      for cap in settings['caps']} for name, seeds in settings['cohorts'].items()}
    return {'plan': settings, 'planSha256': digest(settings), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion'] or version('optuna') != plan['optunaVersion']:
        raise ValueError('Use the pinned GEPA and Optuna versions')
    result = replay(plan, reference)
    with args.out.open('x') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
