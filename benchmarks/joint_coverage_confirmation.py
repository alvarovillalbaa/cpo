"""Measure the search budget recovered by rejecting impossible coverage early."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import joint_demo_bundles as parent, joint_risk_coverage as risk, typed_policy
from cpo._contract import digest
from cpo.coverage_confirmation import confirm_covered_gain


ROOT = Path(__file__).resolve().parents[1]
PARENT_REPORT = '45b6a487a59051d6381d6733b6b505eea1f808288089a52d7427e1af275bf88f'
NEW_SEEDS = (43313, 43321, 43331, 43391, 43403, 43427)
CONTROLS = ('combined', 'gepa-batched', 'gepa-sequential')
VARIANTS = ('early-veto', 'coverage-first')


def prepare():
    preceding, _ = parent.prepare()
    raw = (ROOT / 'docs/joint-demo-bundles-results-v1.json').read_bytes()
    report = json.loads(raw)
    if sha256(raw).hexdigest() != PARENT_REPORT or report['planSha256'] != digest(preceding):
        raise ValueError('The preceding joint demonstration experiment differs from its seal')
    cohorts = {**preceding['cohorts'], 'unseen-seeds': NEW_SEEDS}
    paths = ('benchmarks/joint_coverage_confirmation.py', 'cpo/coverage_confirmation.py', *preceding['sourceSha256'])
    settings = {
        **{key: preceding[key] for key in ('caps', 'gepaVersion', 'optunaVersion')},
        'protocol': 'cpo-joint-coverage-confirmation-v1', 'cohorts': cohorts,
        'primary': 'coverage-first', 'methods': (*CONTROLS, *VARIANTS),
        'parentPlanSha256': digest(preceding), 'parentReportSha256': PARENT_REPORT,
        'datasetSha256': {str(seed): digest(typed_policy.cohorts(seed))
                          for seeds in cohorts.values() for seed in seeds},
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
        'scope': ('Keep the balanced demonstration pool, sampler, exact search gates and independent qualification. '
                  'Reject as soon as a required critical group has no remaining possible pass. Compare the old '
                  'confirmation order with checking uncovered strata first. Audit the tight-cap warehouse failure '
                  'and report the paired quality comparison with both GEPA variants and the old combined policy.'),
    }
    return settings, report['results']


def run_variant(task, groups, grid, seed, cap, method):
    validation = risk.diverse_prefix(task, groups['validation'], risk.parent.BATCH)
    strata = {row['id']: risk.stratum(task, row) for row in validation if row['critical']}

    def confirm(program, rows, baseline, target, evaluate, journal, *, early):
        if not early:
            raise ValueError('Coverage checking requires bounded confirmation')
        by_id = {row['id']: row for row in rows}
        initial = dict(zip(by_id, baseline, strict=True))
        protected = {key for key in strata if initial[key]}
        cached = {key: journal[program, key].passed for key in by_id if (program, key) in journal}
        return confirm_covered_gain(
            initial, target, protected, strata, cached, lambda key: evaluate(program, by_id[key]).passed,
            prioritize_coverage=method == 'coverage-first',
        )

    with patch.object(risk.parent, 'exact_gain', confirm):
        return risk.parent.run_arm(task, {**groups, 'validation': validation}, grid, seed, cap, 'tpe-cpo')


def measure(seeds, cap, archive):
    totals = {method: Counter() for method in (*CONTROLS, *VARIANTS)}
    comparisons = {variant: {method: Counter() for method in CONTROLS} for variant in VARIANTS}
    panels = {}
    for seed in seeds:
        for task, groups in typed_policy.cohorts(seed).items():
            panel = f'{seed}/{task}'
            original = risk.parent.candidate_grid(task, groups['train'], seed)
            grid = parent.balanced_grid(task, groups['train'], seed, original)
            arms = {method: risk.run_arm(task, groups, grid, seed, cap, method) for method in CONTROLS}
            if archive is not None and any(point != archive[panel][f'balanced/{method}']
                                           for method, point in arms.items()):
                raise ValueError('A control did not reproduce its published trace')
            arms.update({method: run_variant(task, groups, grid, seed, cap, method) for method in VARIANTS})
            panels[panel] = arms
            for method, point in arms.items():
                totals[method].update({key: value for key, value in point.items() if type(value) is int})
            for variant, controls in comparisons.items():
                candidate = arms[variant]
                for method, outcome in controls.items():
                    control = arms[method]
                    delta = candidate['holdoutPasses'] - control['holdoutPasses']
                    outcome.update(holdoutDelta=delta, lookupDelta=candidate['paidLookups'] - control['paidLookups'],
                                   panelsWon=int(delta > 0), panelsLost=int(delta < 0),
                                   criticalLosses=sum(row['critical'] and control['holdout'][row['id']]
                                                      and not candidate['holdout'][row['id']]
                                                      for row in groups['holdout']))
    return {'totals': totals, 'comparisons': comparisons, 'panels': panels}


def replay(settings, archive):
    results = {name: {str(cap): measure(seeds, cap, archive[name][str(cap)]['panels'] if name in archive else None)
                      for cap in settings['caps']} for name, seeds in settings['cohorts'].items()}
    return {'plan': settings, 'planSha256': digest(settings), 'results': results}


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
