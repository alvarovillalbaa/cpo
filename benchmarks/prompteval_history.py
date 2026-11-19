"""Replay successive prompt-pool searches with a paid observation history."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import pool, prompteval_transfer as transfer, prompteval_witnesses as witnesses
from cpo import Observation, Row, select_pool
from cpo._contract import digest


PRIMARY = 'cpo-history'
CONTROLS = ('cpo-minibatch', 'gepa-sequential', 'gepa-batched',
            'gepa-sequential-history', 'gepa-batched-history')
ARMS = (PRIMARY, 'cpo-history-two', *CONTROLS)


def past_score(observations, validation):
    """Estimate correctness from past observations outside the current validation set."""
    outcomes = [passed for row, passed in observations.items() if row not in validation]
    return (sum(outcomes) + 1) / (len(outcomes) + 2)


def evaluate_cycle(arm, matrix, candidates, train, validation, seed, history):
    allowed = set(train + validation)
    observed = {}
    historical_hits = 0

    def observe(prompt, row):
        nonlocal historical_hits
        if prompt not in candidates or row not in allowed:
            raise ValueError('A lookup left the current candidate or case pool')
        key = prompt, row
        if key not in observed:
            if len(observed) >= transfer.LOOKUP_LIMIT:
                raise ValueError('A cycle exceeded its distinct lookup budget')
            prior = history.get(prompt, {})
            if row in prior:
                historical_hits += 1
                observed[key] = prior[row]
            else:
                observed[key] = matrix[int(prompt)][row] == '1'
        return observed[key]

    incumbent, *alternatives = candidates
    excluded = set(validation)
    if arm.startswith('gepa-'):
        if arm.endswith('-history'):
            alternatives.sort(key=lambda prompt: past_score(history.get(prompt, {}), excluded), reverse=True)
        picked = transfer.optimize_gepa(incumbent, alternatives, train, validation, observe,
                                       batched=arm.startswith('gepa-batched'), seed=seed)
    else:
        if arm == 'cpo-minibatch':
            shortlist = transfer.minibatch_shortlist(candidates, train, observe)
        else:
            scores = {}
            for prompt in candidates:
                probes = {row: observe(prompt, row) for row in train[:transfer.PROBES]}
                scores[prompt] = past_score(history.get(prompt, {}) | probes, excluded)
            better = [prompt for prompt in alternatives if scores[prompt] > scores[incumbent]]
            better.sort(key=scores.__getitem__, reverse=True)
            shortlist = [incumbent, *better[:2 if arm == 'cpo-history-two' else 1]]
        result = select_pool(shortlist, [Row(str(row), 'task') for row in validation],
                             lambda prompt, row: Observation(observe(prompt, int(row.id)), {}),
                             metric_limit=transfer.LOOKUP_LIMIT - len(observed))
        picked = result.prompt
    for (prompt, row), passed in observed.items():
        history.setdefault(prompt, {})[row] = passed
    return {'candidate': picked, 'evaluations': len(observed) - historical_hits,
            'distinctRequested': len(observed), 'pastHits': historical_hits,
            'searchSha256': digest([(prompt, row, passed) for (prompt, row), passed in observed.items()])}


def prepare(phase):
    source, sizes, fingerprint = witnesses.read_source('exploratory' if phase == 'exploratory' else 'confirmation')
    base = transfer.plan(source, sizes, fingerprint)
    files = (Path(__file__), Path(witnesses.__file__))
    return source, {**base, 'protocol': 'prompteval-paid-history-v1', 'phase': phase, 'subjects': list(sizes),
                    'arms': list(ARMS), 'primary': PRIMARY, 'controls': list(CONTROLS),
                    'frozenCycles': 'Ascending seeds with fresh incumbent and candidate set each cycle',
                    'accounting': 'Every arm starts empty and pays for each distinct candidate-case outcome once',
                    'cycleBudget': 'The existing cap counts distinct outcomes requested, including cache hits',
                    'history': 'Only previously paid observations. Prior ranking excludes current validation rows.',
                    'sourceSha256': {**base['sourceSha256'], **{
                        'benchmarks/' + file.name: sha256(file.read_bytes()).hexdigest() for file in files}}}


def execute(source, plan):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        holdout = plan['holdoutCaseIDs'][subject]
        allowed = sorted(set(range(len(matrix[0]))).difference(holdout))
        histories = {arm: {} for arm in plan['arms']}
        trials = []
        for seed in plan['seeds']:
            rng = Random(seed)
            cases = rng.sample(allowed, transfer.TRAIN_ROWS + transfer.VALIDATION_ROWS)
            train, validation = cases[:transfer.TRAIN_ROWS], cases[transfer.TRAIN_ROWS:]
            candidates = [str(index) for index in rng.sample(range(len(matrix)), transfer.POOL_SIZE)]
            outcomes = {arm: evaluate_cycle(arm, matrix, candidates, train, validation, seed, histories[arm])
                        for arm in plan['arms']}
            for result in outcomes.values():
                result['holdoutPasses'] = sum(matrix[int(result['candidate'])][row] == '1' for row in holdout)
            trials.append({'seed': seed, 'candidates': candidates, 'train': train,
                           'validation': validation, 'arms': outcomes})
        totals, paired = pool.summarize(trials, plan['primary'], plan['controls'])
        for arm, totals_for_arm in totals.items():
            totals_for_arm['pastHits'] = sum(trial['arms'][arm]['pastHits'] for trial in trials)
            if totals_for_arm['evaluations'] != sum(map(len, histories[arm].values())):
                raise ValueError('The replay must charge every distinct observation once')
        panels[f'{subject}/{model}'] = {'totals': totals, 'comparisons': paired, 'trials': trials}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('exploratory', 'recheck'), required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    source, plan = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    report = execute(source, plan)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
