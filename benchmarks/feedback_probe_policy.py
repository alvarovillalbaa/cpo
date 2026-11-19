"""Compare training probe schedules in the deterministic typed fixture."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import feedback_budget as budget, typed_policy
from cpo import optimizer
from cpo._contract import digest


SEEDS = tuple(range(45101, 45329, 19))
CAPS = (32, 40, 56)
POLICIES = ('fixed', 'first-error', 'critical-first-error')


def prepare():
    cohorts = {seed: typed_policy.cohorts(seed) for seed in SEEDS}
    sources = (budget, budget.controls, budget.fixture, budget.grounded, typed_policy, optimizer)
    paths = [Path(module.__file__) for module in sources] + [Path(__file__)]
    plan = {'protocol': 'typed-training-probe-policy-v1', 'delivery': 'deterministic-fixture',
            'gepaVersion': '0.1.4', 'caps': list(CAPS), 'policies': list(POLICIES),
            'conditions': list(budget.CONDITIONS), 'minPassesPerPanel': 14, 'minGain': 8, 'minSavingsPercent': 10,
            'cohortSha256': {str(seed): digest(cohort) for seed, cohort in cohorts.items()},
            'sourceSha256': {path.name: sha256(path.read_bytes()).hexdigest() for path in paths}}
    return plan, cohorts


def execute(plan, cohorts):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {}
    for condition in plan['conditions']:
        caps = results[condition] = {}
        for cap in plan['caps']:
            compared = caps[str(cap)] = {}
            for policy in plan['policies']:
                search = partial(optimizer.search, feedback_policy=policy)
                with patch.object(budget.controls, 'search', search):
                    trials = [budget.compare(task, cases, seed, cap, condition, 'precomputed-two')
                              for seed, tasks in cohorts.items() for task, cases in tasks.items()]
                compared[policy] = {**budget.summarize(trials, plan), 'trialSha256': digest(trials)}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, cohorts = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    report = execute(plan, cohorts)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
