"""Compare CPO and GEPA on public correctness panels with a fixed holdout."""

import argparse
from collections import deque
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from random import Random

from benchmarks import grounded, pool
from cpo import Observation, ProposalBatch, ProposalPair, Row, search, select_certified_pool, select_pool
from cpo._contract import digest


DATA = Path(__file__).with_name('data') / 'prompteval-transfer-v1.json'
SUBJECTS = ('formal_logic', 'high_school_computer_science', 'world_religions')
MODELS = ('meta_llama_llama_3_8b', 'mistralai_mistral_7b_instruct_v0_2')
SEEDS = tuple(range(43101, 43709, 19))
ARMS = ('cpo-precomputed', 'cpo-exact-pool', 'cpo-certificate', 'cpo-minibatch', 'gepa-sequential', 'gepa-batched',
        'uniform', 'successive-halving')
POOL_SIZE = 13
TRAIN_ROWS = 12
VALIDATION_ROWS = 24
LOOKUP_LIMIT = POOL_SIZE * VALIDATION_ROWS * 55 // 100
PROBES = 2


def read_source():
    raw = DATA.read_bytes()
    source = grounded.load_json(raw)
    names = [(panel['subject'], panel['model']) for panel in source['panels']]
    expected = [(subject, model) for subject in SUBJECTS for model in MODELS]
    if source['schema'] != 'prompteval-transfer-v1' or names != expected:
        raise ValueError('The PromptEval panels do not match the transfer protocol')
    sizes = {}
    for panel in source['panels']:
        vectors = panel['correctness']
        if len(vectors) != 100 or not isinstance(vectors[0], str):
            raise ValueError('Each panel needs 100 complete template scores')
        count = len(vectors[0])
        if count - count * 30 // 100 < TRAIN_ROWS + VALIDATION_ROWS or any(
                not isinstance(vector, str) or len(vector) != count or set(vector) - {'0', '1'} for vector in vectors):
            raise ValueError('The matrix must be rectangular with enough binary case scores')
        if sizes.setdefault(panel['subject'], count) != count:
            raise ValueError('Both models need the same ordered cases for each subject')
    return source, sizes, sha256(raw).hexdigest()


def holdout(subject, count):
    cases = list(range(count))
    Random(f'prompteval-transfer-v1:{subject}:holdout').shuffle(cases)
    return sorted(cases[:count * 30 // 100])


def plan(source, sizes, fingerprint):
    root = Path(__file__).resolve().parents[1]
    paths = ('benchmarks/prompteval_transfer.py', 'benchmarks/pool.py', 'benchmarks/grounded.py',
             'cpo/__init__.py', 'cpo/_contract.py', 'cpo/optimizer.py', 'cpo/certified_pool.py', 'cpo/pool.py',
             'requirements-benchmark.txt')
    return {'protocol': 'prompteval-recorded-transfer-v1', 'delivery': 'recorded-outcome-replay',
            'corpusSha256': fingerprint, 'sourceDataset': source['sourceDataset'],
            'observedRepoRevision': source['observedRepoRevision'], 'gepaVersion': '0.1.4',
            'subjects': list(SUBJECTS), 'models': list(MODELS), 'seeds': list(SEEDS), 'arms': list(ARMS),
            'holdoutCaseIDs': {subject: holdout(subject, count) for subject, count in sizes.items()},
            'poolSize': POOL_SIZE, 'trainRows': TRAIN_ROWS, 'validationRows': VALIDATION_ROWS,
            'evaluationLookupLimit': LOOKUP_LIMIT, 'probeSize': PROBES,
            'callAccounting': 'Distinct candidate-case lookups. The common proposal stream is supplied.',
            'qualification': 'Preserve holdout totals and lookups, with a gain or 10% fewer lookups',
            'sourceSha256': {path: sha256((root / path).read_bytes()).hexdigest() for path in paths}}


def optimize_gepa(initial, alternatives, train, validation, observe, *, batched, seed):
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    candidates = iter(alternatives)
    width = 2 if batched else 1
    calls = 0

    def metric(prompt, example):
        nonlocal calls
        calls += 1
        return float(observe(prompt, example['case']))

    def propose(current, _feedback, components):
        component, = components
        return {component: next(candidates, current[component])}

    settings = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_metric_calls=LOOKUP_LIMIT, max_candidate_proposals=len(alternatives) // width,
                            track_best_outputs=False, sampling_strategy=SameParentSampling(width) if batched else None),
        reflection=ReflectionConfig(custom_candidate_proposer=propose, reflection_lm=None,
                                    reflection_minibatch_size=PROBES),
        tracking=TrackingConfig(logger=grounded.GepaLogger()),
        stop_callbacks=[ScoreThresholdStopper(1.0),
                        lambda _: calls + width * (2 * PROBES + len(validation)) > LOOKUP_LIMIT])
    return optimize_anything(initial, evaluator=metric, dataset=[{'case': row} for row in train],
                             valset=[{'case': row} for row in validation], config=settings).best_candidate


def minibatch_shortlist(candidates, train, observe):
    # Compare on shared training rows. Only a strict winner earns a validation challenge.
    scores = {candidate: sum(observe(candidate, row) for row in train[:PROBES]) for candidate in candidates}
    incumbent = candidates[0]
    challenger = max(candidates, key=scores.__getitem__)
    return [incumbent] if challenger == incumbent else [incumbent, challenger]


def compare(matrix, excluded, seed):
    rng = Random(seed)
    allowed_cases = sorted(set(range(len(matrix[0]))).difference(excluded))
    sampled = rng.sample(allowed_cases, TRAIN_ROWS + VALIDATION_ROWS)
    train, validation = sampled[:TRAIN_ROWS], sampled[TRAIN_ROWS:]
    candidates = [str(index) for index in rng.sample(range(len(matrix)), POOL_SIZE)]
    incumbent, *alternatives = candidates
    results = {}
    for arm in ARMS:
        archive = {}
        allowed = set(sampled if arm.startswith('gepa-') or arm in ('cpo-precomputed', 'cpo-minibatch') else validation)

        def observe(prompt, row):
            if prompt not in candidates or row not in allowed:
                raise ValueError('A search queried outside its sealed candidate and case pools')
            key = prompt, row
            if key not in archive:
                if len(archive) >= LOOKUP_LIMIT:
                    raise ValueError('A search exceeded the sealed lookup budget')
                archive[key] = matrix[int(prompt)][row] == '1'
            return archive[key]

        def evaluate(prompt, row):
            passed = observe(prompt, int(row.id))
            return Observation(passed, {'correct': passed})

        rows = [Row(str(case), 'task') for case in validation]
        if arm == 'cpo-precomputed':
            queue = deque(alternatives[2:])

            def propose(_parent, _feedback, _history, width):
                choices = tuple(queue.popleft() for _ in range(min(width, len(queue))))
                return ProposalBatch(choices, exhausted=not queue)

            result = search(incumbent, [Row(str(case), 'task') for case in train], rows, evaluate, propose,
                            metric_limit=LOOKUP_LIMIT, rounds=len(alternatives) // 2,
                            train_per_round=PROBES, seed=seed, adaptive=True, opening_pair=ProposalPair(*alternatives[:2]))
            chosen = result.prompt
        elif arm == 'cpo-exact-pool':
            chosen = select_pool(candidates, rows, evaluate, metric_limit=LOOKUP_LIMIT).prompt
        elif arm == 'cpo-certificate':
            chosen = select_certified_pool(candidates, rows, evaluate, metric_limit=LOOKUP_LIMIT).prompt
        elif arm == 'cpo-minibatch':
            shortlist = minibatch_shortlist(candidates, train, observe)
            chosen = select_pool(shortlist, rows, evaluate, metric_limit=LOOKUP_LIMIT - len(archive)).prompt
        elif arm.startswith('gepa-'):
            chosen = optimize_gepa(incumbent, alternatives, train, validation, observe,
                                   batched=arm == 'gepa-batched', seed=seed)
        elif arm == 'uniform':
            chosen = pool.uniform(candidates, validation, observe, LOOKUP_LIMIT)
        else:
            chosen = pool.successive_halving(candidates, validation, observe, LOOKUP_LIMIT)
        results[arm] = {'candidate': chosen, 'evaluations': len(archive),
                        'searchSha256': digest([(prompt, case, value) for (prompt, case), value in archive.items()])}
    for result in results.values():
        result['holdoutPasses'] = sum(matrix[int(result['candidate'])][case] == '1' for case in excluded)
    return {'seed': seed, 'candidates': candidates, 'train': train, 'validation': validation, 'arms': results}


def execute(frozen, source):
    try:
        if version('gepa') != frozen['gepaVersion']:
            raise ValueError('Use the pinned GEPA version')
    except PackageNotFoundError as error:
        raise ValueError('Use the pinned GEPA version') from error
    panels = {}
    for panel in source['panels']:
        subject, model = panel['subject'], panel['model']
        excluded = frozen['holdoutCaseIDs'][subject]
        trials = [compare(panel['correctness'], excluded, seed) for seed in SEEDS]
        totals, paired = pool.summarize(trials, 'cpo-precomputed', ARMS[1:])
        _, screened = pool.summarize(trials, 'cpo-minibatch', [arm for arm in ARMS if arm != 'cpo-minibatch'])
        panels[f'{subject}/{model}'] = {'totals': totals, 'paired': paired, 'minibatchPaired': screened, 'trials': trials}
    return {'plan': frozen, 'planSha256': digest(frozen), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    source, sizes, fingerprint = read_source()
    frozen = plan(source, sizes, fingerprint)
    seal = digest(frozen)
    if args.execute is None and args.out is None:
        print(json.dumps({**frozen, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    report = execute(frozen, source)
    with args.out.open('x') as target:
        json.dump(report, target, indent=2, sort_keys=True)
        target.write('\n')
    print(json.dumps({panel: result['paired'] for panel, result in report['panels'].items()}, sort_keys=True))


if __name__ == '__main__':
    main()
