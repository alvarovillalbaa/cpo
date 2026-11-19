"""Replay certified prompt selection on recorded correctness matrices."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from benchmarks import pool
from cpo import Observation, Row
from cpo._contract import digest
from cpo.certified_pool import select_certified_pool


FRESH_SEEDS = tuple(range(34057, 34817, 19))
COHORTS = {'phase-three': pool.SEEDS[3], 'fresh-seeds': FRESH_SEEDS}


def plan(name, input_hash):
    root = Path(__file__).resolve().parents[1]
    files = ('benchmarks/certified_pool.py', 'benchmarks/pool.py', 'cpo/certified_pool.py', 'cpo/pool.py')
    _, _, candidates, validation = pool.COHORTS[name]
    return {'protocol': 'fixed-pool-certificate-v1', 'dataset': name, 'matrixSha256': input_hash,
            'cohorts': {label: list(seeds) for label, seeds in COHORTS.items()},
            'poolSize': candidates, 'validationCases': validation, 'maxLookups': candidates * validation * 55 // 100,
            'controls': [*pool.CONTROLS, 'cpo-exact', 'cpo-shortlist'],
            'qualification': 'Preserve aggregate held-out accuracy and lookups, with a gain or 10% savings',
            'sourceSha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in files}}


def compare(matrix, seed, frozen):
    size, validation_count, budget = (frozen[key] for key in ('poolSize', 'validationCases', 'maxLookups'))
    trial = pool.replay(matrix, seed, pool_size=size, validation_count=validation_count, limit=budget,
                        screen_rows=validation_count // 4, shortlist=True)
    candidates, validation = trial['candidates'], trial['validation']
    allowed = set(validation)
    observed = {}

    def evaluate(prompt, row):
        number = int(row.id)
        key = prompt, number
        if number not in allowed or key in observed or len(observed) >= budget:
            raise ValueError('Certificate requested a duplicate, holdout, or over-budget outcome')
        observed[key] = matrix[int(prompt)][number] == '1'
        return Observation(observed[key], {})

    result = select_certified_pool(candidates, [Row(str(row), 'task') for row in validation],
                                   evaluate, metric_limit=budget)
    selected = matrix[int(result.prompt)]
    passes = sum(selected[row] == '1' for row in validation)
    initial = sum(matrix[int(candidates[0])][row] == '1' for row in validation)
    if (result.evaluations != len(observed) or not result.lower_pass_bound <= passes <= result.upper_pass_bound
            or (result.prompt != candidates[0] and result.lower_pass_bound <= initial)):
        raise ValueError('Recorded outcomes do not substantiate the returned certificate')
    trial['arms']['cpo-certificate'] = {
        'candidate': result.prompt, 'evaluations': result.evaluations, 'incumbentValidationPasses': initial,
        'validationPassBounds': [result.lower_pass_bound, result.upper_pass_bound],
        'auditSha256': digest([(prompt, row, passed) for (prompt, row), passed in observed.items()]),
        'holdoutPasses': sum(selected[row] == '1' for row in trial['holdout']),
    }
    return trial


def run(frozen, matrix):
    cohorts = {}
    for label, seeds in frozen['cohorts'].items():
        trials = [compare(matrix, seed, frozen) for seed in seeds]
        totals, paired = pool.summarize(trials, 'cpo-certificate', frozen['controls'])
        early = sum(trial['arms']['cpo-certificate']['validationPassBounds'][0] <
                    trial['arms']['cpo-certificate']['validationPassBounds'][1] for trial in trials)
        cohorts[label] = {'totals': totals, 'paired': paired, 'earlyCertificates': early, 'trials': trials}
    return {'plan': frozen, 'planSha256': digest(frozen), 'cohorts': cohorts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=pool.COHORTS, required=True)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    matrix, fingerprint = pool.read_matrix(args.dataset, args.matrix)
    frozen = plan(args.dataset, fingerprint)
    seal = digest(frozen)
    if args.execute is None and args.out is None:
        print(json.dumps({**frozen, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    result = run(frozen, matrix)
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({name: {key: values[key] for key in ('totals', 'paired', 'earlyCertificates')}
                      for name, values in result['cohorts'].items()}, sort_keys=True))


if __name__ == '__main__':
    main()
