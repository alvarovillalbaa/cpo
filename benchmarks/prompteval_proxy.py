"""Compare a second model's training shortlist with target-only search."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import grounded, prompteval_transfer as transfer
from cpo import Observation, Row, select_pool
from cpo._contract import digest


SUBJECTS = ('business_ethics', 'high_school_geography', 'high_school_mathematics', 'prehistory')
DATA = transfer.DATA.with_name('prompteval-proxy-v1.json')
SCREEN = {'target-two': ('target', 2), 'proxy-two': ('proxy', 2),
          'proxy-four': ('proxy', 4), 'ordered-pool': ('target', 0)}
PROXY_RATES = (1, 2, 4)  # Express costs in quarters of a target lookup.
REFERENCES = ('target-two', 'ordered-pool', 'cpo-minibatch', 'gepa-sequential', 'gepa-batched')
PRIMARY = 'proxy-two'


def design():
    root = Path(__file__).resolve().parents[1]
    files = ('benchmarks/prompteval_proxy.py', 'benchmarks/prompteval_transfer.py', 'benchmarks/pool.py',
             'cpo/__init__.py', 'cpo/pool.py', 'cpo/optimizer.py',
             'cpo/certified_pool.py', 'cpo/_contract.py', 'benchmarks/grounded.py', 'requirements-benchmark.txt')
    return {'protocol': 'prompteval-proxy-v1', 'delivery': 'recorded-correctness-replay',
            'subjects': list(SUBJECTS), 'models': list(transfer.MODELS), 'seeds': list(transfer.SEEDS),
            'gepaVersion': '0.1.4', 'lookupLimit': transfer.LOOKUP_LIMIT, 'poolSize': transfer.POOL_SIZE,
            'trainSize': transfer.TRAIN_ROWS, 'validationSize': transfer.VALIDATION_ROWS,
            'holdout': 'Existing deterministic 30% split by subject',
            'ranking': 'Stable training score order; evaluate the top two challengers on the target model',
            'screen': SCREEN, 'primary': PRIMARY, 'controls': list(REFERENCES),
            'targetCostQuarters': 4, 'proxyCostQuarters': list(PROXY_RATES),
            'gate': 'Preserve holdout passes and cost with a pass gain or at least 10% fewer cost units',
            'sourceSha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in files}}


def read_source():
    raw = DATA.read_bytes()
    dataset = grounded.load_json(raw)
    expected = [(subject, model) for subject in SUBJECTS for model in transfer.MODELS]
    if dataset['schema'] != 'prompteval-transfer-v1' or [
            (panel['subject'], panel['model']) for panel in dataset['panels']] != expected:
        raise ValueError('Unexpected model and subject splits')
    sizes = {}
    for panel in dataset['panels']:
        vectors = panel['correctness']
        if len(vectors) != 100 or not all(isinstance(row, str) for row in vectors):
            raise ValueError('Each panel must have 100 complete template scores')
        size = len(vectors[0])
        if size - size * 30 // 100 < transfer.TRAIN_ROWS + transfer.VALIDATION_ROWS or any(
                len(row) != size or set(row) - {'0', '1'} for row in vectors):
            raise ValueError('Each template needs the same ordered binary case scores')
        if sizes.setdefault(panel['subject'], size) != size:
            raise ValueError('Both models need the same subject cases')
    return dataset, sizes, sha256(raw).hexdigest()


def evaluate(arm, matrix, proxy, trial, holdout):
    candidates, train, validation = (trial[name] for name in ('candidates', 'train', 'validation'))
    if set(train).intersection(validation) or set(holdout).intersection(train + validation):
        raise ValueError('Search and holdout must remain disjoint')
    journal = {}
    model, probes = SCREEN[arm]
    training = train[:probes]
    sources = {'target': matrix, 'proxy': proxy}

    def lookup(source, prompt, row):
        if prompt not in candidates or (row not in training and
                                       (source != 'target' or row not in validation)):
            raise ValueError('Lookup left its sealed model, candidate, or case pool')
        key = source, prompt, row
        if key not in journal:
            if len(journal) >= transfer.LOOKUP_LIMIT:
                raise ValueError('Search exceeded the combined lookup cap')
            journal[key] = sources[source][int(prompt)][row] == '1'
        return journal[key]

    incumbent, *alternatives = candidates
    ranked = sorted(alternatives, key=lambda prompt: sum(lookup(model, prompt, row) for row in training), reverse=True)
    rows = [Row(str(row), 'task') for row in validation]
    selected = select_pool([incumbent, *ranked[:2]], rows,
                           lambda prompt, row: Observation(lookup('target', prompt, int(row.id)), {}),
                           metric_limit=transfer.LOOKUP_LIMIT - len(journal)).prompt
    proxy_count = sum(source == 'proxy' for source, _, _ in journal)
    return {'candidate': selected, 'targetLookups': len(journal) - proxy_count, 'proxyLookups': proxy_count,
            'searchSha256': digest([(source, prompt, row, value) for (source, prompt, row), value in journal.items()]),
            'holdoutPasses': sum(matrix[int(selected)][row] == '1' for row in holdout)}


def qualify(totals, contender, reference, rate):
    a, b = (totals[arm] for arm in (contender, reference))
    a_cost, b_cost = (4 * row['targetLookups'] + rate * row['proxyLookups'] for row in (a, b))
    delta = a['holdoutPasses'] - b['holdoutPasses']
    return {'passDelta': delta, 'costDeltaQuarters': a_cost - b_cost,
            'qualified': delta >= 0 and a_cost <= b_cost and (delta > 0 or 10 * a_cost <= 9 * b_cost)}


def execute(dataset, plan):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    matrices = {(item['subject'], item['model']): item['correctness'] for item in dataset['panels']}
    panels = {}
    for (subject, model), target in matrices.items():
        proxy = next(matrix for (topic, other), matrix in matrices.items() if topic == subject and other != model)
        holdout = plan['holdoutCaseIDs'][subject]
        trials = []
        for seed in plan['seeds']:
            trial = transfer.compare(target, holdout, seed)
            previous = trial['arms']
            trial['arms'] = {arm: {'candidate': previous[arm]['candidate'],
                                   'targetLookups': previous[arm]['evaluations'], 'proxyLookups': 0,
                                   'holdoutPasses': previous[arm]['holdoutPasses'],
                                   'searchSha256': previous[arm]['searchSha256']}
                             for arm in REFERENCES if arm not in SCREEN}
            trial['arms'].update({arm: evaluate(arm, target, proxy, trial, holdout) for arm in SCREEN})
            trials.append(trial)
        keys = ('holdoutPasses', 'targetLookups', 'proxyLookups')
        totals = {arm: {key: sum(trial['arms'][arm][key] for trial in trials) for key in keys}
                  for arm in trials[0]['arms']}
        comparisons = {arm: {str(rate): {ref: qualify(totals, arm, ref, rate) for ref in REFERENCES}
                             for rate in PROXY_RATES} for arm in ('proxy-two', 'proxy-four')}
        panels[subject + '/' + model] = {'totals': totals, 'comparisons': comparisons, 'trials': trials}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', action='store_true')
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    frozen = design()
    if args.design:
        print(json.dumps({**frozen, 'designSha256': digest(frozen)}, sort_keys=True, indent=2))
        return
    dataset, sizes, fingerprint = read_source()
    plan = {**frozen, 'designSha256': digest(frozen), 'corpusSha256': fingerprint,
            'datasetRevision': dataset['observedRepoRevision'],
            'holdoutCaseIDs': {subject: transfer.holdout(subject, size) for subject, size in sizes.items()}}
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    report = execute(dataset, plan)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
