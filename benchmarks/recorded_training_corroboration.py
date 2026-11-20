"""Use held-aside training observations to veto fragile archived promotions."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import recorded_math_validation_ties as prior
from cpo import Row
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = 'bf90d2fab3a9b33eece3a15392234db88afcaa13e5b8e2cf897ac54c9656e451'
POLICIES = {
    'one-gain-nonloss': ('validation-one', 0, 'full'),
    'one-gain-support': ('validation-one', 1, 'full'),
    'all-nonloss': ('all', 0, 'full'),
    'all-support': ('all', 1, 'full'),
    'qualification-one-support': ('qualification-one', 1, 'full'),
    'half-training-nonloss': ('all', 0, 'first-half'),
    'half-training-support': ('all', 1, 'first-half'),
    'second-half-support': ('all', 1, 'second-half'),
}
CONTROLS = ('strict', *prior.GEPA, 'retain-start')
METHODS = (*CONTROLS, *POLICIES)


def corroborate(incumbent, challenger, rows, observe, *, minimum_gain, remaining, seed):
    """Settle the exact paired training margin from a bounded reply prefix."""
    low, high = -len(rows), len(rows)
    order = Random(seed)
    count = 0
    for row in rows:
        sides = [incumbent, challenger]
        order.shuffle(sides)
        for prompt in sides:
            if count >= remaining:
                return False
            correct = observe(prompt, row).passed
            if type(correct) is not bool:
                raise ValueError('The training guard requires exact boolean replies')
            count += 1
            if correct == (prompt == challenger):
                low += 1
            else:
                high -= 1
            if low >= minimum_gain:
                return True
            if high < minimum_gain:
                return False
    raise RuntimeError('A complete training panel must settle the gain')


def run_trial(cells, start, roster, cohorts, seed, arm, cap):
    if arm in CONTROLS:
        return prior.run_trial(cells, start, roster, cohorts, seed, arm, cap)
    trigger, minimum_gain, panel = POLICIES[arm]
    original_selection = prior.select
    original_qualification = prior.certify_paired_qualification
    audit, state = Counter(), {}

    def select(incumbent, candidates, rows, observe, journal, *, method, cap):
        nominee, tied = original_selection(incumbent, candidates, rows, observe, journal, method=method, cap=cap)
        if nominee != incumbent:
            gain = sum(journal[nominee, row.id].passed - journal[incumbent, row.id].passed for row in rows)
            state.update(gain=gain, observe=observe, journal=journal)
        return nominee, tied

    def qualify(incumbent, challenger, rows, evaluate, *, seed):
        decision = original_qualification(incumbent, challenger, rows, evaluate, seed=seed)
        if decision.status != 'promoted':
            return decision
        applies = (trigger == 'all' or trigger == 'validation-one' and state['gain'] == 1
                   or trigger == 'qualification-one' and decision.upper_gain == 1)
        if applies:
            cases = cohorts[0]
            midpoint = len(cases) // 2
            if panel == 'first-half':
                cases = cases[:midpoint]
            elif panel == 'second-half':
                cases = cases[midpoint:]
            training = tuple(Row(str(case), 'training') for case in cases)
            before = len(state['journal'])
            supported = corroborate(incumbent, challenger, training, state['observe'], minimum_gain=minimum_gain,
                                    remaining=cap - before, seed=seed)
            audit.update(trainingChecks=1, trainingVetoes=int(not supported),
                         addedTrainingLookups=len(state['journal']) - before)
            if not supported:
                return replace(decision, status='rejected', prompt=incumbent)
        return decision

    with (patch.object(prior, 'select', select), patch.object(prior, 'certify_paired_qualification', qualify)):
        total, trace, passed = prior.run_trial(cells, start, roster, cohorts, seed, 'strict', cap)
    return {**total, **audit}, trace, passed


def prepare():
    parent, data = prior.prepare()
    raw = (ROOT / 'docs/recorded-math-validation-ties-results-v1.json').read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != SOURCE_SHA256 or reference['planSha256'] != digest(parent):
        raise ValueError('The archived comparison does not reproduce its published seal')
    paths = ('benchmarks/recorded_training_corroboration.py', 'benchmarks/recorded_math_validation_ties.py',
             'cpo/paired_qualification.py')
    plan = {**{k: parent[k] for k in ('gepaVersion', 'datasets', 'challengerCounts', 'incumbentGroups', 'searchCap',
                                     'bootstrapSeed', 'bootstrapDraws', 'minimumLookupSavingPercent')},
            'protocol': 'cpo-recorded-training-corroboration-v1', 'priorPlanSha256': digest(parent),
            'priorReportSha256': SOURCE_SHA256,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'methods': METHODS, 'policies': POLICIES,
            'scope': ('Run identical validation and independent qualification. Confirm weak or all '
                      'qualified changes on the entire training panel or either half before deployment. '
                      'Read no more than the original search budget and keep the original paired gate.')}
    return plan, data, reference['results']


def measure(cells, settings, group, width, plan, reference):
    size = len(next(iter(cells.values())))
    starts = tuple(cells)[:1] if group == 'root' else tuple(cells)[1:]
    totals, journals = {m: Counter() for m in METHODS}, {m: [] for m in METHODS}
    vectors = {m: [0] * size for m in METHODS}
    changes = {m: Counter() for m in POLICIES}
    losses = {label: Counter() for label in prior.GEPA}
    recoveries = {m: Counter() for m in POLICIES}
    for seed in settings['seeds']:
        cohorts = prior.split_cases(size, seed, settings['cohorts'])
        for start in starts:
            available = [prompt for prompt in cells if prompt != start]
            roster = Random(f'{seed}/{start}').sample(available, len(available))[:width]
            trial = {}
            for arm in METHODS:
                count, log, passed = run_trial(cells, start, roster, cohorts, seed, arm, plan['searchCap'])
                totals[arm].update(count)
                journals[arm].append(log)
                for case, outcome in zip(cohorts[-1], passed, strict=True):
                    vectors[arm][case] += outcome
                trial[arm] = (count['holdoutPasses'], log[3])
            strict = trial['strict'][0]
            for rival in prior.GEPA:
                rival_score, rival_final = trial[rival]
                if rival_final != start or rival_score <= strict:
                    continue
                losses[rival].update(trials=1, grossDeficit=rival_score - strict)
                for arm in POLICIES:
                    gain = trial[arm][0] - strict
                    recovered = trial[arm][0] >= rival_score
                    recoveries[arm].update({f'{rival}/passesRecovered': gain, f'{rival}/trialsMatched': int(recovered)})
            for arm in POLICIES:
                change = trial[arm][0] - strict
                changes[arm].update(trialsImproved=int(change > 0), trialsRegressed=int(change < 0),
                                    grossGain=max(0, change), grossLoss=max(0, -change))
    points = {arm: {**count, 'traceSha256': digest(journals[arm])} for arm, count in totals.items()}
    if any(points[arm] != reference['totals'][arm] for arm in CONTROLS):
        raise ValueError('A control differs from its published paired trace')
    if any(sum(vectors[arm]) != totals[arm]['holdoutPasses'] for arm in METHODS):
        raise ValueError('Resampling vector disagrees with the archived trial totals')
    comparisons = {arm: prior.comparison(arm, totals, prior.paired_ranges(vectors, arm, ('strict', *prior.GEPA), plan), plan)
                   for arm in POLICIES}
    return {'totals': points, 'comparisons': comparisons, 'trialsPerMethod': reference['trialsPerMethod'],
            'changesFromStrict': changes, 'startRetentionLosses': losses, 'startLossRecoveries': recoveries}


def replay(plan, data, references):
    results = {}
    for domain, settings in plan['datasets'].items():
        cells = prior.load_cells(domain, data[domain]['record'])
        results[domain] = {f'{group}/{width}': measure(cells, settings, group, width, plan,
                                                     references[domain][f'{group}/{width}'])
                           for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    return {'plan': plan, 'planSha256': digest(plan), 'results': results}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, data, references = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, data, references)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
