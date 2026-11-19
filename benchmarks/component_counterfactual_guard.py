"""Certify conditional promotions against an observed global fallback under label changes."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import component_conditional_edits as conditional, component_dependencies as prior
from benchmarks.component_merge import encode
from cpo import Row
from cpo._contract import digest
from cpo.challenger import certify_challenger


SEEDS = tuple(range(68801, 69409, 19))
POLICIES = ('search', 'clean-gate', 'counterfactual-gate')
ARMS = tuple(f'{method}.{policy}' for method in conditional.METHODS for policy in POLICIES)
PRIMARY = 'cpo-dependencies.counterfactual-gate'


def is_global(prompt):
    return all(not value.startswith('scope:') for value in json.loads(prompt).values())


def observed_globals(journal, rows):
    totals = Counter(row.family for row in rows)
    measured = {prompt for prompt, _ in journal if is_global(prompt)}

    def rank(entry):
        prompt, scores = entry
        passed = [row for row in rows if scores[row.id]]
        groups = Counter(row.family for row in passed)
        balance = sum(Fraction(groups[family], size) for family, size in totals.items())
        return -sum(row.critical for row in passed), -balance, -len(passed), len(prompt), prompt

    records = [(prompt, {row.id: journal[prompt, row.id] for row in rows})
               for prompt in measured if all((prompt, row.id) in journal for row in rows)]
    return min(records, key=rank) if records else (None, {})


def guard_candidate(prompt, journal, validation, profile, spare):
    """Return decisions for two gates sharing the paid nominal validation."""
    if is_global(prompt):
        return {policy: (prompt, {'status': 'global-winner', 'evaluations': 0}) for policy in POLICIES[1:]}
    rows = [Row(case, row['family'], row['critical']) for case, row in validation.items()]
    fallback, base = observed_globals(journal, rows)
    if fallback is None:
        raise ValueError('The global opening must have a complete observed panel')
    observed = {row.id: journal[prompt, row.id] for row in rows if (prompt, row.id) in journal}

    def planning_only(_):
        raise ValueError('The clean gate can read only recorded observations')

    nominal = certify_challenger(rows, base, planning_only, metric_limit=0, observed=observed)
    if nominal.status != 'promote':
        result = {'status': f'clean:{nominal.status}', 'evaluations': 0, 'fallback': fallback}
        return {policy: (fallback, result) for policy in POLICIES[1:]}

    twins = {f'{row.id}:opposite': {**validation[row.id], 'interaction': not validation[row.id]['interaction']}
             for row in rows if row.critical and base[row.id]}
    if validation.keys() & twins.keys():
        raise ValueError('Counterfactual IDs overlap nominal validation')
    expanded = [*rows, *(Row(case, row['family'], True) for case, row in twins.items())]
    protected = {**base, **dict.fromkeys(twins, True)}
    trial = []
    candidate = json.loads(prompt)

    def evaluate(row):
        if len(trial) >= spare:
            raise ValueError('Counterfactual guard exceeded the remaining evaluation budget')
        # Permit a partial nominal record only when the paid evidence already certifies the clean gain.
        case = twins[row.id] if row.id in twins else validation[row.id]
        observation = conditional.score(candidate, case, profile)
        trial.append((row.id, observation.passed))
        return observation

    guard = certify_challenger(expanded, protected, evaluate, metric_limit=spare, observed=observed)
    winner = prompt if guard.status == 'promote' else fallback
    return {'clean-gate': (prompt, {'status': 'clean:promote', 'evaluations': 0, 'fallback': fallback}),
            'counterfactual-gate': (winner, {'status': guard.status, 'evaluations': guard.evaluations,
                                             'fallback': fallback, 'protectedProbes': len(twins), 'observations': trial})}


def compare(groups, profile, seed, cap):
    arms = {}
    validation = {row['id']: row for row in groups['validation']}
    holdout = groups['holdout']
    shifted = conditional.shifted_labels(holdout, seed)
    flipped = [{**row, 'interaction': not row['interaction']} for row in holdout]
    search_ids = {row['id'] for split in ('train', 'validation') for row in groups[split]}
    for method in conditional.METHODS:
        search_observations, validation_observations = set(), {}

        def measure(program, row, task):
            result = conditional.score(program, row, task)
            key = encode(program), row['id']
            if row['id'] in search_ids:
                search_observations.add(key)
            if row['id'] in validation:
                validation_observations[key] = result.passed
            return result

        with patch.object(prior, 'ARMS', (method,)), patch.object(prior, 'cases', return_value=groups), \
                patch.object(prior, 'score', measure), patch.object(prior, 'next_edit', conditional.conditional_edit):
            trial = prior.compare(profile, seed, cap)
        record = trial['arms'][method]
        selected = record['chosen']
        spare = cap - len(search_observations)
        if spare < 0:
            raise ValueError('Search exceeded its evaluation cap')
        choices = {'search': (selected, {'status': 'ordinary', 'evaluations': 0})}
        if selected is not None:
            choices.update(guard_candidate(selected, validation_observations, validation, profile, spare))
        else:
            choices.update({policy: (None, {'status': 'reference-failed', 'evaluations': 0}) for policy in POLICIES[1:]})

        def score(prompt, cohort):
            return {row['id']: conditional.score(prompt, row, profile).passed for row in cohort}

        for policy, (prompt, receipt) in choices.items():
            clean = shifted_results = both = None
            if prompt is not None:
                program = json.loads(prompt)
                clean, shifted_results, inverted = (score(program, cohort) for cohort in (holdout, shifted, flipped))
                both = {case: passed and inverted[case] for case, passed in clean.items()}
            arms[f'{method}.{policy}'] = {**record, 'chosen': prompt, 'outcomes': clean, 'shiftedOutcomes': shifted_results,
                                        'bothLabels': both, 'calls': record['calls'] + receipt['evaluations'],
                                        'spareEvaluations': spare, 'gate': receipt}
    return {**trial, 'arms': arms}


def summarize(trials):
    summaries = {}
    for cohort, key in (('clean', 'outcomes'), ('shifted', 'shiftedOutcomes'), ('bothLabels', 'bothLabels')):
        outcomes = [{**trial, 'arms': {arm: {**entry, 'outcomes': entry[key]}
                                       for arm, entry in trial['arms'].items()}} for trial in trials]
        with patch.object(prior, 'ARMS', ARMS), patch.object(prior, 'PRIMARY', PRIMARY):
            summaries[cohort] = prior.summarize(outcomes)
    gates = {}
    for arm in ARMS:
        items = [trial['arms'][arm] for trial in trials]
        gates[arm] = {'statuses': dict(Counter(item['gate']['status'] for item in items)),
                      'extraEvaluations': sum(item['gate']['evaluations'] for item in items),
                      'conditionalSelections': sum(item['chosen'] is not None and not is_global(item['chosen']) for item in items)}
    return {**summaries, 'gates': gates, 'trials': trials}


def prepare():
    plan = conditional.prepare()
    root = Path(__file__).resolve().parents[1]
    for file in ('benchmarks/component_counterfactual_guard.py', 'cpo/challenger.py'):
        plan['sourceSha256'][file] = sha256((root / file).read_bytes()).hexdigest()
    return {**plan, 'protocol': 'cpo-component-counterfactual-guard-v1', 'seeds': list(SEEDS), 'arms': list(ARMS),
            'primary': PRIMARY, 'extraEvaluationBudget': 'ordinary search remainder only',
            'cohortDigests': {profile: digest([conditional.panels(profile, seed) for seed in SEEDS]) for profile in prior.PROFILES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    results = {}
    for cap in plan['caps']:
        results[str(cap)] = {}
        for profile in plan['profiles']:
            cohorts = [(seed, conditional.panels(profile, seed)) for seed in plan['seeds']]
            results[str(cap)][profile] = {panel: summarize([compare(groups[panel], profile, seed, cap)
                                                            for seed, groups in cohorts]) for panel in plan['panels']}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
