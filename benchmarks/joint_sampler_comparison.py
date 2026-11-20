"""Compare fixed instruction and demonstration selection with official Optuna TPE."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
import warnings

from benchmarks import alternative_controls as alt
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import grounded, grounded_fixture, typed_policy
from cpo import Observation, Row, select_pool
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
METHODS = ('cpo', 'full-grid', 'random-sampler', 'tpe-sampler', 'tpe-cpo', 'gepa-sequential', 'gepa-batched')
SEEDS = (*alt.SEEDS, 42967, 42979, 42989)
CAPS = (48, 72)
OPTUNA_VERSION = '4.5.0'
BATCH = 3
TRIAL_LIMIT = 24


def plan():
    files = ('benchmarks/joint_sampler_comparison.py', 'benchmarks/gepa_paid_cap_transfer.py',
             'cpo/pool.py', 'cpo/paired_qualification.py', *alt.plan()['sourceSha256'])
    return {'protocol': 'cpo-joint-sampler-comparison-v1', 'delivery': 'deterministic-fixture', 'methods': METHODS,
            'seeds': SEEDS, 'caps': CAPS, 'gepaVersion': '0.1.4', 'optunaVersion': OPTUNA_VERSION,
            'samplerStartupTrials': 3, 'minibatchSize': BATCH, 'fullCheckEveryTrials': 3,
            'samplerTrialLimit': TRIAL_LIMIT, 'demoBundleCount': 3,
            'datasetSha256': {str(seed): digest(typed_policy.cohorts(seed)) for seed in SEEDS},
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in files}}


def candidate_grid(task, training, seed):
    inputs = {'current': grounded.BASELINE, 'labeledTraining': training}
    opening = grounded_fixture.respond({'task': task, 'role': 'reflection', 'instruction': grounded.OPENING, 'input': inputs})
    rewrite, repair = grounded.proposals(opening, grounded.BASELINE, ('rewrite', 'repair'))
    update = grounded_fixture.respond({'task': task, 'role': 'reflection', 'instruction': grounded.UPDATE,
                                       'input': {**inputs, 'current': repair}})
    edit, = grounded.proposals(update, repair, ('instruction',))
    instructions = tuple(dict.fromkeys((grounded.BASELINE, rewrite, repair, edit)))
    keys = list(range(len(training)))
    Random(f'{seed}:{task}:demonstrations').shuffle(keys)
    demos = ((), *(tuple(sorted(keys[offset:offset + 4])) for offset in (0, 4, 8)))
    if any(len(bundle) != 4 for bundle in demos[1:]):
        raise ValueError('The fixture must supply enough training for three disjoint bundles')
    return tuple(tuple(alt.encode(instruction, bundle) for bundle in demos) for instruction in instructions)


def exact_gain(prompt, validation, baseline, target, evaluate, journal, *, early):
    protected = {row['id'] for row, passed in zip(validation, baseline, strict=True) if row['critical'] and passed}
    if early:
        known = {row['id']: journal[prompt, row['id']].passed for row in validation if (prompt, row['id']) in journal}
        unknown = [row for row in validation if row['id'] not in known]
        passes, left = sum(known.values()), len(unknown)
        if any(known.get(case) is False for case in protected) or passes + left <= target:
            return None
        baseline_scores = {row['id']: passed for row, passed in zip(validation, baseline, strict=True)}
        ordered = sorted(unknown, key=lambda row: (row['id'] not in protected, baseline_scores[row['id']]))
        for row in ordered:
            passed = evaluate(prompt, row).passed
            passes, left = passes + passed, left - 1
            if (not passed and row['id'] in protected) or passes + left <= target:
                return None
        return passes
    values = [evaluate(prompt, row).passed for row in validation]
    if sum(values) > target and all(value or row['id'] not in protected
                                    for row, value in zip(validation, values, strict=True)):
        return sum(values)
    return None


def sample_grid(grid, validation, evaluate, journal, *, cap, seed, method):
    import optuna

    params = {'instruction': optuna.distributions.CategoricalDistribution(tuple(range(len(grid)))),
              'demonstrations': optuna.distributions.CategoricalDistribution(tuple(range(len(grid[0]))))}
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', optuna.exceptions.ExperimentalWarning)
        sampler = (optuna.samplers.TPESampler(seed=seed, multivariate=True, n_startup_trials=3)
                   if method != 'random-sampler' else optuna.samplers.RandomSampler(seed=seed))
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction='maximize', sampler=sampler)
    batches, checked = {}, set()
    initial = selected = grid[0][0]
    baseline = [evaluate(initial, row).passed for row in validation]
    score = sum(baseline)
    fields = len(validation[0]['expected'])

    def batch(prompt):
        if prompt not in batches:
            values = [evaluate(prompt, row) for row in validation[:BATCH]]
            batches[prompt] = sum((BATCH * fields + 1) * value.passed + value.matched_fields for value in values)
        return batches[prompt]

    baseline_trial = optuna.trial.create_trial(params=dict.fromkeys(params, 0), distributions=params, value=batch(initial))
    study.add_trial(baseline_trial)
    checked.add(initial)

    def confirm():
        nonlocal selected, score
        for prompt in sorted(batches, key=batches.__getitem__, reverse=True):
            if prompt in checked:
                continue
            if len(journal) + sum((prompt, row['id']) not in journal for row in validation) > cap:
                continue
            measured = exact_gain(prompt, validation, baseline, score, evaluate, journal, early=method == 'tpe-cpo')
            checked.add(prompt)
            if measured is not None:
                selected, score = prompt, measured
            return

    proposals = []
    for index in range(TRIAL_LIMIT):
        if score == len(validation) or len(journal) + len(validation) > cap:
            break
        trial = study.ask(fixed_distributions=params)
        pair = trial.params['instruction'], trial.params['demonstrations']
        proposals.append(pair)
        study.tell(trial, batch(grid[pair[0]][pair[1]]))
        if (index + 1) % 3 == 0:
            confirm()
    if score < len(validation):
        confirm()
    return selected, {'samplerTrials': len(proposals), 'distinctSamplerTrials': len(set(proposals)),
                      'validationConfirmations': len(checked), 'samplerTraceSha256': digest(proposals)}


def run_arm(task, groups, grid, seed, cap, method):
    training, validation, qualification, held = (groups[k] for k in ('train', 'validation', 'confirmation', 'holdout'))
    rows = {row['id']: row for row in (*training, *validation)}
    initial = grid[0][0]
    roster = [program for row in grid for program in row]
    challengers = roster[1:]
    Random(f'{seed}:{task}:roster').shuffle(challengers)
    search, confirmation = {}, {}

    def evaluate(program, row):
        key = program, row['id']
        if program not in roster or key[1] not in rows:
            raise ValueError('A candidate looked outside its fixed pool or search cohort')
        if key not in search:
            if len(search) >= cap:
                raise ValueError('Candidate exceeded the paid lookup cap')
            output = alt.complete(task, program, row['input'], training)
            passed, fields = grounded.score(output, row['expected'])
            search[key] = Observation(passed, {}, fields)
        return search[key]

    def check(program, row):
        output = alt.complete(task, program, row['input'], training)
        return grounded.score(output, row['expected'])[0]

    audit = {}
    if method == 'cpo':
        val = [Row(row['id'], task, row['critical']) for row in validation]
        nominee = select_pool((initial, *challengers), val, lambda p, row: evaluate(p, rows[row.id]),
                              metric_limit=cap, screen_rows=1, adaptive_rejection=True).prompt
    elif method == 'full-grid':
        baseline = [evaluate(initial, row).passed for row in validation]
        target, nominee = sum(baseline), initial
        for program in challengers:
            if target == len(validation) or len(search) + len(validation) > cap:
                break
            values = [evaluate(program, row).passed for row in validation]
            if sum(values) > target and all(not row['critical'] or not old or new
                                           for row, old, new in zip(validation, baseline, values, strict=True)):
                target, nominee = sum(values), program
    elif method in ('random-sampler', 'tpe-sampler', 'tpe-cpo'):
        nominee, audit = sample_grid(grid, validation, evaluate, search, cap=cap, seed=seed, method=method)
    else:
        nominee, offered = gepa.optimize_by_paid_reads(
            initial, challengers, [row['id'] for row in training], [row['id'] for row in validation],
            lambda p, case: evaluate(p, rows[case]).passed, lambda: len(search),
            paid_limit=cap, batched=method == 'gepa-batched', seed=seed,
        )
        audit['gepaProposals'] = offered

    eligible = {row['id']: row for row in qualification}

    def qualify(program, row, repeat):
        key = program, row.id
        if key in confirmation or repeat != 0:
            raise ValueError('Qualification may read each independent reply once')
        confirmation[key] = check(program, eligible[row.id])
        return confirmation[key]

    decision = certify_paired_qualification(initial, nominee, [Row(row['id'], task, row['critical']) for row in qualification],
                                            qualify, seed=seed)
    outcomes = {row['id']: check(decision.prompt, row) for row in held}
    return {**audit, 'holdout': outcomes, 'holdoutPasses': sum(outcomes.values()), 'evaluations': len(search),
            'qualificationLookups': len(confirmation), 'paidLookups': len(search) + len(confirmation) + 2,
            'promoted': int(decision.status == 'promoted'), 'selectedSha256': digest(decision.prompt),
            'searchSha256': digest([(key, o.passed, o.matched_fields) for key, o in search.items()]),
            'qualificationSha256': digest(list(confirmation.items()))}


def replay(settings):
    panels, totals, comparisons, hybrid = {}, {}, {}, {}
    for cap in settings['caps']:
        name = str(cap)
        panels[name] = {}
        totals[name] = {m: Counter() for m in METHODS}
        comparisons[name] = {m: Counter() for m in METHODS if m != 'cpo'}
        hybrid[name] = {m: Counter() for m in ('cpo', 'tpe-sampler', 'gepa-sequential', 'gepa-batched')}
        for seed in settings['seeds']:
            for task, cohorts in typed_policy.cohorts(seed).items():
                grid = candidate_grid(task, cohorts['train'], seed)
                row = {m: run_arm(task, cohorts, grid, seed, cap, m) for m in METHODS}
                for method, point in row.items():
                    totals[name][method].update({k: v for k, v in point.items() if type(v) is int})
                    if method != 'cpo':
                        tracked = comparisons[name][method]
                        for case in cohorts['holdout']:
                            delta = row['cpo']['holdout'][case['id']] - point['holdout'][case['id']]
                            tracked.update(cpoPassDelta=delta, matchedCriticalLosses=int(delta < 0 and case['critical']))
                        tracked.update(cpoLookupDelta=row['cpo']['paidLookups'] - point['paidLookups'])
                    if method in hybrid[name]:
                        tracked = hybrid[name][method]
                        tracked.update(passDelta=row['tpe-cpo']['holdoutPasses'] - point['holdoutPasses'],
                                       lookupDelta=row['tpe-cpo']['paidLookups'] - point['paidLookups'])
                        tracked.update(matchedCriticalLosses=sum(
                            case['critical'] and point['holdout'][case['id']]
                            and not row['tpe-cpo']['holdout'][case['id']] for case in cohorts['holdout']))
                panels[name][f'{seed}/{task}'] = row
    return {'plan': settings, 'planSha256': digest(settings), 'panels': panels, 'totals': totals,
            'cpoComparisons': comparisons, 'hybridComparisons': hybrid}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    settings = plan()
    seal = digest(settings)
    if args.execute is None and args.out is None:
        print(json.dumps({**settings, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != settings['gepaVersion'] or version('optuna') != settings['optunaVersion']:
        raise ValueError('Use the pinned GEPA and Optuna versions')
    result = replay(settings)
    with args.out.open('x') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
