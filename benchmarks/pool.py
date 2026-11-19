"""Replay accuracy selection on rectangular matrices of recorded model scores."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from random import Random

from cpo import Observation, Row, select_pool
from cpo._contract import digest


SEEDS = {1: tuple(range(31123, 31883, 19)), 2: tuple(range(32213, 32973, 19)),
         3: tuple(range(33301, 34061, 19))}
COHORTS = {
    'abstract-algebra': (100, 100, 13, 24),
    'aime': (9, 45, 9, 10),
    'arc-agi': (10, 80, 10, 14),
}
CONTROLS = ('uniform', 'successive-halving')


def read_matrix(name, path):
    raw = path.read_bytes()
    if name == 'abstract-algebra':
        vectors = raw.decode('ascii').splitlines()
    elif name == 'aime':
        vectors = [entry['passed'] for entry in json.loads(raw)['candidates']]
    else:
        vectors = []
        for entry in json.loads(raw)['candidates']:
            binary = [score[0] for score in entry['rows']]
            if sum(binary) != entry['sourceSolved']:
                raise ValueError('ARC vectors must reproduce source accuracy')
            vectors.append(''.join(map(str, binary)))
    count, size, _, _ = COHORTS[name]
    if len(vectors) != count or any(len(row) != size or set(row) - {'0', '1'} for row in vectors):
        raise ValueError(f'Invalid {name} correctness matrix shape')
    return vectors, sha256(raw).hexdigest()


def uniform(candidates, validation, observe, limit):
    count = min(len(validation), limit // len(candidates))
    return max(candidates, key=lambda prompt: sum(observe(prompt, row) for row in validation[:count]))


def successive_halving(candidates, validation, observe, limit):
    active = list(candidates)
    rounds = (len(active) - 1).bit_length()
    cumulative, spent = 0, 0
    scores = dict.fromkeys(active, 0)
    for step in range(rounds):
        additional = min((limit - spent) // ((rounds - step) * len(active)), len(validation) - cumulative)
        for prompt in active:
            scores[prompt] += sum(observe(prompt, row) for row in validation[cumulative:cumulative + additional])
        cumulative += additional
        spent += additional * len(active)
        active = sorted(active, key=scores.__getitem__, reverse=True)[:(len(active) + 1) // 2]
    return active[0]


def replay(matrix, seed, *, pool_size, validation_count, limit, screen_rows, shortlist):
    rng = Random(seed)
    candidates = [str(row) for row in rng.sample(range(len(matrix)), pool_size)]
    cases = list(range(len(matrix[0])))
    rng.shuffle(cases)
    validation, holdout = cases[:validation_count], cases[validation_count:]
    allowed = set(validation)
    arms = {}
    variants = {'cpo-exact': (0, None)}
    if screen_rows:
        variants['cpo-screened'] = (screen_rows, None)
    if shortlist:
        variants['cpo-shortlist'] = (screen_rows, 1)
    for name in (*CONTROLS, *variants):
        journal = {}

        def observe(prompt, row):
            if row not in allowed:
                raise ValueError('Search attempted to read a holdout case')
            key = prompt, row
            if key not in journal:
                if len(journal) >= limit:
                    raise ValueError('Replay exceeded its budget')
                journal[key] = matrix[int(prompt)][row] == '1'
            return journal[key]

        if name == 'uniform':
            picked = uniform(candidates, validation, observe, limit)
        elif name == 'successive-halving':
            picked = successive_halving(candidates, validation, observe, limit)
        else:
            prefix, maximum = variants[name]
            candidate = select_pool(candidates, [Row(str(row), 'task') for row in validation],
                                    lambda prompt, row: Observation(observe(prompt, int(row.id)), {}),
                                    metric_limit=limit, screen_rows=prefix, max_challenges=maximum)
            picked = candidate.prompt
            if candidate.evaluations != len(journal):
                raise ValueError('CPO did not match the replay lookup count')
        arms[name] = {'candidate': picked, 'evaluations': len(journal),
                      'auditSha256': digest([(prompt, row, passed) for (prompt, row), passed in journal.items()]),
                      'holdoutPasses': sum(matrix[int(picked)][row] == '1' for row in holdout)}
    return {'seed': seed, 'candidates': candidates, 'validation': validation, 'holdout': holdout, 'arms': arms}


def plan(name, phase, input_hash):
    _, _, pool_size, validation = COHORTS[name]
    methods = {1: ('cpo-exact', []), 2: ('cpo-screened', ['cpo-exact']),
               3: ('cpo-shortlist', ['cpo-exact', 'cpo-screened'])}
    primary, additional_controls = methods[phase]
    return {
        'study': 'fixed-pool-alternatives', 'phase': phase, 'dataset': name, 'matrixSha256': input_hash,
        'seeds': list(SEEDS[phase]), 'poolSize': pool_size, 'validationCases': validation,
        'maxLookups': pool_size * validation * 55 // 100,
        'screenRows': validation // 4 if phase >= 2 else 0,
        'shortlist': 1 if phase == 3 else None,
        'primary': primary, 'controls': [*CONTROLS, *additional_controls],
        'gate': 'No aggregate holdout loss and no added lookups, with positive accuracy gain or 10% savings',
        'sourceSha256': {str(path.relative_to(Path(__file__).resolve().parents[1])): sha256(path.read_bytes()).hexdigest()
                         for path in (Path(__file__).resolve(), Path(__file__).resolve().parents[1] / 'cpo/pool.py')},
    }


def summarize(trials, primary, controls):
    arms = trials[0]['arms']
    totals = {arm: {key: sum(trial['arms'][arm][key] for trial in trials)
                    for key in ('holdoutPasses', 'evaluations')} for arm in arms}
    paired = {}
    for baseline in controls:
        differences = [trial['arms'][primary]['holdoutPasses'] - trial['arms'][baseline]['holdoutPasses']
                       for trial in trials]
        delta, cost, reference = sum(differences), totals[primary]['evaluations'], totals[baseline]['evaluations']
        paired[baseline] = {'passDelta': delta, 'lookupDelta': cost - reference,
                            'splitsWithLowerAccuracy': sum(value < 0 for value in differences),
                            'qualified': delta >= 0 and cost <= reference and
                                         (delta > 0 or 10 * cost <= 9 * reference)}
    return totals, paired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=COHORTS, required=True)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--phase', type=int, choices=SEEDS, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    matrix, fingerprint = read_matrix(args.dataset, args.matrix)
    frozen = plan(args.dataset, args.phase, fingerprint)
    seal = digest(frozen)
    if args.execute is None and args.out is None:
        print(json.dumps({**frozen, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None:
        parser.error('Execution requires the current seal and a fresh output path')
    trials = [replay(matrix, seed, pool_size=frozen['poolSize'], validation_count=frozen['validationCases'],
                     limit=frozen['maxLookups'], screen_rows=frozen['screenRows'],
                     shortlist=frozen['shortlist']) for seed in frozen['seeds']]
    totals, paired = summarize(trials, frozen['primary'], frozen['controls'])
    result = {'plan': frozen, 'planSha256': seal, 'totals': totals, 'paired': paired, 'trials': trials}
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({'totals': totals, 'paired': paired}, sort_keys=True))


if __name__ == '__main__':
    main()
