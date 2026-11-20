"""Test whether training-side bundle coverage can supply qualified joint programs."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import joint_risk_coverage as risk, typed_policy
from cpo._contract import digest
from cpo.demonstrations import stratified_demo_bundles


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = 'ba152b67a5d9648d7140e7b1a6f2ee95d73fa131af84f1608a9cb4e68c035f29'
NEW_SEEDS = (43103, 43117, 43133, 43151, 43159, 43177)
METHODS = ('random/original', 'random/combined', 'balanced/original', 'balanced/combined',
           'random/gepa-sequential', 'random/gepa-batched', 'balanced/gepa-sequential', 'balanced/gepa-batched')


def balanced_grid(task, training, seed, original):
    indices = tuple(range(len(training)))
    strata = {i: tuple(sorted(risk.parent.alt.demo_features(task, risk.grounded_fixture.facts(row['input'])).items()))
              for i, row in enumerate(training)}
    bundles = stratified_demo_bundles(indices, strata, bundle_size=4, bundle_count=3, seed=f'{seed}:{task}:strata')
    demos = ((), *(tuple(sorted(bundle)) for bundle in bundles))
    return tuple(tuple(risk.parent.alt.encode(risk.parent.grounded.load_json(programs[0])['instruction'], bundle)
                       for bundle in demos) for programs in original)


def prepare():
    previous, _ = risk.prepare()
    raw = (ROOT / 'docs/joint-risk-coverage-results-v1.json').read_bytes()
    report = json.loads(raw)
    if sha256(raw).hexdigest() != SOURCE_SHA256 or report['planSha256'] != digest(previous):
        raise ValueError('The preceding critical coverage experiment differs from its seal')
    paths = ('benchmarks/joint_demo_bundles.py', 'cpo/demonstrations.py', *previous['sourceSha256'])
    cohorts = {**previous['cohorts'], 'new-seeds': NEW_SEEDS}
    plan = {**{k: previous[k] for k in ('caps', 'gepaVersion', 'optunaVersion')},
            'protocol': 'cpo-joint-demo-bundles-v1', 'cohorts': cohorts, 'methods': METHODS,
            'primary': 'balanced/combined', 'parentPlanSha256': digest(previous),
            'parentReportSha256': SOURCE_SHA256, 'bundleSize': 4, 'bundleCount': 3,
            'datasetSha256': {str(seed): digest(typed_policy.cohorts(seed))
                              for seeds in cohorts.values() for seed in seeds},
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'scope': ('Replace random training demos with equal-size disjoint bundles that cover declared input strata. '
                      'Keep instructions and independent qualification fixed and give both GEPA controls the same pool.')}
    return plan, report['results']


def measure(seeds, cap, archive):
    panels, totals = {}, {m: Counter() for m in METHODS}
    coverage, comparisons = {task: Counter() for task in typed_policy.TASKS}, {
        m: Counter() for m in ('balanced/original', 'random/original', 'random/combined',
                               'balanced/gepa-sequential', 'balanced/gepa-batched')}
    for seed in seeds:
        for task, cohorts in typed_policy.cohorts(seed).items():
            name = f'{seed}/{task}'
            random = risk.parent.candidate_grid(task, cohorts['train'], seed)
            grids = {'random': random, 'balanced': balanced_grid(task, cohorts['train'], seed, random)}
            rows = {}
            for label in METHODS:
                pool, method = label.split('/')
                point = risk.run_arm(task, cohorts, grids[pool], seed, cap, method)
                if archive is not None and pool == 'random' and point != archive[name][method]:
                    raise ValueError('A random-bundle control differs from its published outcomes or costs')
                rows[label] = point
                totals[label].update({k: v for k, v in point.items() if type(v) is int})

            # Exhaustive fixture support is an offline diagnostic. The result
            # is computed after all paid search and qualification finish.
            old, new = (risk.full_pool_support(task, cohorts, grids[mode]) for mode in ('random', 'balanced'))
            coverage[task].update(panels=1, randomEligible=old, balancedEligible=new,
                                  randomPanelsWithSupport=int(old > 0), balancedPanelsWithSupport=int(new > 0))
            challenger = rows['balanced/combined']
            for control, outcome in comparisons.items():
                ref = rows[control]
                outcome.update(holdoutDelta=challenger['holdoutPasses'] - ref['holdoutPasses'],
                               lookupDelta=challenger['paidLookups'] - ref['paidLookups'])
                outcome.update(matchedCriticalLosses=sum(row['critical'] and ref['holdout'][row['id']]
                                                         and not challenger['holdout'][row['id']]
                                                         for row in cohorts['holdout']))
            panels[name] = {**rows, 'fullPoolSupport': {'random': old, 'balanced': new}}
    return {'totals': totals, 'panels': panels, 'poolCoverage': coverage, 'primaryComparisons': comparisons}


def replay(settings, archive):
    result = {}
    for name, seeds in settings['cohorts'].items():
        result[name] = {str(cap): measure(seeds, cap, archive[name][str(cap)]['panels'] if name in archive else None)
                        for cap in settings['caps']}
    return {'plan': settings, 'planSha256': digest(settings), 'results': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    settings, archive = prepare()
    seal = digest(settings)
    if args.execute is None and args.out is None:
        print(json.dumps({**settings, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != settings['gepaVersion'] or version('optuna') != settings['optunaVersion']:
        raise ValueError('Use the pinned GEPA and Optuna versions')
    result = replay(settings, archive)
    with args.out.open('x') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
