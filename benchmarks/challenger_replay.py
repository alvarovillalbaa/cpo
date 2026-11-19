"""Verify single-challenger certificates using archived binary model scores."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from benchmarks import pool
from cpo import Observation, Row
from cpo._contract import digest
from cpo.challenger import certify_challenger


SEEDS = tuple(range(64001, 64761, 19))


def replay(matrix, seed, validation_count):
    generator = Random(seed)
    base, candidate = generator.sample(matrix, 2)
    case_ids = generator.sample(range(len(base)), validation_count)
    rows = tuple(Row(str(case), 'task') for case in case_ids)
    incumbent = {str(case): base[case] == '1' for case in case_ids}
    cache_size = validation_count // 3
    cache = {str(case): candidate[case] == '1' for case in case_ids[:cache_size]}
    remaining = validation_count - cache_size
    measured = set()

    def evaluate(row):
        if row.id in cache or row.id in measured:
            raise ValueError('Replay attempted a duplicate evaluation')
        measured.add(row.id)
        return Observation(candidate[int(row.id)] == '1', {})

    result = certify_challenger(rows, incumbent, evaluate, metric_limit=remaining, observed=cache)
    exact = sum(candidate[case] == '1' for case in case_ids)
    promoted = result.status == 'promote'
    if promoted != (exact > sum(incumbent.values())) or result.evaluations != len(measured):
        raise ValueError('Certificate does not match the complete archived panel')
    return {'promoted': promoted, 'lookups': result.evaluations, 'fullLookups': remaining, 'cached': cache_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=pool.COHORTS, required=True)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    matrix, fingerprint = pool.read_matrix(args.dataset, args.matrix)
    paths = ('benchmarks/challenger_replay.py', 'benchmarks/pool.py', 'cpo/challenger.py', 'cpo/optimizer.py',
             'cpo/_contract.py')
    root = Path(__file__).resolve().parents[1]
    count = pool.COHORTS[args.dataset][-1]
    plan = {'protocol': 'cpo-challenger-on-recorded-model-scores-v1', 'dataset': args.dataset,
            'matrixSha256': fingerprint, 'validationCases': count, 'cached': count // 3, 'seeds': list(SEEDS),
            'sourceSha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in paths}}
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    trials = [replay(matrix, seed, count) for seed in SEEDS]
    totals = {key: sum(trial[key] for trial in trials) for key in trials[0]}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'totals': totals, 'trials': trials}, output, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
