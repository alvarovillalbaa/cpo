"""Spend unreserved CPO budget on finishing interrupted validations or trying fresh edits."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import component_dependencies as prior, component_funded_exploration as funded, component_merge as fixture
from benchmarks.frontier import FAMILIES
from cpo import Row
from cpo._contract import digest
from cpo.challenger import certify_challenger


SEEDS = tuple(range(62401, 63161, 19))
BASELINE = 'cpo-dependencies'
PRIMARY = 'cpo-spare-combined'
STRATEGIES = {'cpo-spare-finish': ('finish',), 'cpo-spare-hint': ('hint',),
              'cpo-spare-alternative': ('alternative',), PRIMARY: ('finish', 'hint')}
REFERENCES = ('cpo-component', 'gepa-dependencies', 'gepa-dependencies-merge')
ARMS = (BASELINE, *STRATEGIES, *REFERENCES)


def best_interrupted(events, journal, rows, incumbent, budget, evaluate):
    pending = []
    for prompt in sorted({event['prompt'] for event in events if event['kind'] == 'budget'}):
        observed = {row.id: journal[prompt, row.id].passed for row in rows if (prompt, row.id) in journal}
        if not 0 < len(observed) < len(rows):
            continue
        result = certify_challenger(rows, incumbent, evaluate, metric_limit=0, observed=observed)
        needed = result.minimum_fresh_for_promotion
        if needed is not None and needed <= budget:
            pending.append((needed, -result.lower_pass_bound, prompt, observed))
    if pending:
        _, _, prompt, observed = min(pending)
        return prompt, observed
    return None, {}


def compare(profile, seed, cap):
    groups = prior.cases(profile, seed)
    training = {row['id']: row for row in groups['train']}
    validation = {row['id']: row for row in groups['validation']}
    rows = [Row(case, row['family'], row['critical']) for case, row in validation.items()]
    allowed = training | validation
    journal, seen, audit = {}, set(), Counter()
    captured = []
    search = fixture.search

    def observe(program, case):
        if case not in allowed:
            raise ValueError('Search requested a holdout case')
        key = fixture.encode(program), case
        if key not in journal:
            if len(journal) >= cap:
                raise fixture.BudgetReached
            journal[key] = prior.score(program, allowed[case], profile)
        return journal[key]

    def capture(*args, **kwargs):
        result = search(*args, **kwargs)
        captured.append(result)
        return result

    def propose(parent, _slot, _profile):
        return prior.next_edit(parent, journal, training, seen, 'dependencies', audit)

    with patch.object(fixture, 'search', capture), patch.object(fixture, 'propose_edit', propose):
        selected, proposals, _, _ = fixture.run_cpo(
            'cpo-ordinary', groups, profile, seed, cap, dict.fromkeys(FAMILIES, 'off'), observe, journal)
    search_result = captured[0]
    incumbent = fixture.encode(selected)
    base = {row.id: journal[incumbent, row.id].passed for row in rows}
    spare = cap - len(journal)
    prefix_calls = len(journal) + len(proposals)

    def holdout(prompt):
        program = json.loads(prompt)
        return {row['id']: prior.score(program, row, profile).passed for row in groups['holdout']}

    record = {'chosen': incumbent, 'outcomes': holdout(incumbent), 'calls': prefix_calls, 'stale': audit['stale'],
              'transferred': audit['transferred'], 'mergesAccepted': 0,
              'searchSha256': digest([(prompt, case, item.passed) for (prompt, case), item in journal.items()])}
    pair = funded.choose_pair(search_result, journal, training, validation, seed)
    fresh = {'hint': pair.hint if pair else None, 'alternative': pair.alternative if pair else None}

    def fresh_evaluation(prompt, row):
        if (prompt, row.id) in journal:
            raise ValueError('Continuation requested a cached row')
        return prior.score(json.loads(prompt), validation[row.id], profile)

    def planning_only(_):
        raise ValueError('Planning cannot evaluate a row')

    interrupted, cached = best_interrupted(search_result.events, journal, rows, base, spare, planning_only)
    arms = {BASELINE: record}
    for arm, schedule in STRATEGIES.items():
        spent = reflections = 0
        chosen, attempts = incumbent, []
        arm_journal = {}
        for kind in schedule:
            prompt, saved = (interrupted, cached) if kind == 'finish' else (fresh[kind], {})
            if prompt is None:
                continue
            allowance = spare - spent
            plan = certify_challenger(rows, base, planning_only, metric_limit=0, observed=saved)
            needed = plan.minimum_fresh_for_promotion
            if needed is None or needed > allowance:
                attempts.append({'kind': kind, 'status': 'unfunded', 'prompt': prompt, 'evaluations': 0})
                continue

            def evaluate(row):
                key = prompt, row.id
                if key in arm_journal:
                    raise ValueError('Continuation requested a duplicate row')
                if len(arm_journal) >= spare:
                    raise fixture.BudgetReached
                value = fresh_evaluation(prompt, row)
                arm_journal[key] = value
                return value

            certificate = certify_challenger(rows, base, evaluate, metric_limit=allowance, observed=saved)
            spent += certificate.evaluations
            reflections += kind != 'finish'
            attempts.append({'kind': kind, 'status': certificate.status, 'prompt': prompt,
                             'evaluations': certificate.evaluations, 'cached': len(saved),
                             'lowerPassBound': certificate.lower_pass_bound, 'upperPassBound': certificate.upper_pass_bound,
                             'observations': certificate.observations})
            if certificate.status == 'promote':
                chosen = prompt
                break
        if len(arm_journal) != spent or spent > spare:
            raise ValueError('Continuation and measured usage disagree')
        arms[arm] = {**record, 'chosen': chosen, 'outcomes': holdout(chosen) if chosen != incumbent else record['outcomes'],
                     'calls': prefix_calls + reflections + spent, 'attempts': attempts,
                     'searchSha256': digest([record['searchSha256'], attempts])}

    with patch.object(prior, 'ARMS', REFERENCES):
        trial = prior.compare(profile, seed, cap)
    return {**trial, 'arms': {**trial['arms'], **arms}, 'spare': spare, 'hasHintPair': pair is not None}


def summarize(trials):
    with patch.object(prior, 'ARMS', ARMS), patch.object(prior, 'PRIMARY', PRIMARY):
        summary = prior.summarize(trials)
    for arm in STRATEGIES:
        attempts = [attempt for trial in trials for attempt in trial['arms'][arm]['attempts']]
        summary['totals'][arm]['attempts'] = dict(Counter(f"{item['kind']}:{item['status']}" for item in attempts))
        summary['totals'][arm]['freshEvaluations'] = sum(item['evaluations'] for item in attempts)
    return {**summary, 'spareEvaluations': sum(trial['spare'] for trial in trials),
            'hintPairs': sum(trial['hasHintPair'] for trial in trials), 'trials': trials}


def prepare():
    plan = funded.prepare()
    root = Path(__file__).resolve().parents[1]
    for name in ('benchmarks/component_spare_validation.py', 'cpo/challenger.py'):
        plan['sourceSha256'][name] = sha256((root / name).read_bytes()).hexdigest()
    del plan['reservedValidationPanels']
    return {**plan, 'protocol': 'cpo-component-spare-validation-v1', 'arms': list(ARMS), 'primary': PRIMARY,
            'strategies': {name: list(stages) for name, stages in STRATEGIES.items()},
            'seeds': list(SEEDS), 'allocation': 'only unspent search evaluations, with no reservation',
            'cohortDigests': {profile: digest([prior.cases(profile, seed) for seed in SEEDS]) for profile in prior.PROFILES}}


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
            trials = [compare(profile, seed, cap) for seed in plan['seeds']]
            results[str(cap)][profile] = summarize(trials)
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'results': results}, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
