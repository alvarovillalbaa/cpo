"""Compare search and validation behavior under controlled transfer conditions."""

import argparse
from collections import Counter
from dataclasses import asdict
from importlib.metadata import version
from contextlib import redirect_stdout
from io import StringIO
from hashlib import sha256
import json
from pathlib import Path
from random import Random
import re

from cpo import Observation, ProposalPair, Row, search
from cpo._contract import digest


FAMILIES = ('aggregate', 'precedence', 'eligibility')
PROFILES = ('additive', 'interaction', 'transfer')
SECOND_SEEDS = (7039, 7121, 7211, 7331, 7411, 7523, 7643, 7741)
CPO_SEEDS = (10103, 10111, 10133, 10141, 10151, 10159, 10163, 10169)
CPO_CONFIRMATION_SEEDS = (10601, 10607, 10613, 10627, 10631, 10639, 10651, 10657)
CPO_PROFILES = ('reverse-precedence', 'legacy-heavy', 'multi-clause')
METRIC_LIMIT = 72
REFLECTION_LIMIT = 4
MINIBATCH = 3
BASE = 'baseline'


class EvaluationLimitReached(Exception):
    """Stop an indivisible GEPA batch before it exceeds the physical cap."""


def make_cases(profile, seed):
    rng = Random(seed)
    cohorts = {}
    for split, count in [('train', 12), ('validation', 9), ('holdout', 30)]:
        rows = []
        for i in range(count):
            family = FAMILIES[i % len(FAMILIES)]
            variant = i // len(FAMILIES)
            condition = ('ordinary', 'edge', 'legacy')[variant % 3]
            if profile == 'transfer' and split == 'holdout':
                condition = rng.choice(('edge', 'legacy', 'legacy', 'ordinary'))
            needs = [] if condition == 'legacy' else [family]
            if condition == 'edge' and profile != 'additive':
                needs.append(FAMILIES[(i + 1) % len(FAMILIES)])
            forbids = [family] if condition == 'legacy' and profile != 'additive' else []
            rows.append({'id': f'{seed}-{split}-{i:02d}', 'family': family,
                         'critical': family == 'eligibility' and condition == 'legacy',
                         'needs': needs, 'forbids': forbids})
        rng.shuffle(rows)
        cohorts[split] = rows
    return cohorts


def make_cpo_cases(profile, seed):
    rng = Random(seed)
    cohorts = {}
    for split, count in [('train', 15), ('validation', 12), ('holdout', 36)]:
        rows = []
        for index in range(count):
            family = FAMILIES[index % len(FAMILIES)]
            others = [name for name in FAMILIES if name != family]
            condition = rng.choice(('ordinary', 'edge', 'legacy'))
            if profile == 'legacy-heavy' and split == 'holdout':
                condition = rng.choice(('edge', 'legacy', 'legacy', 'legacy'))
            if condition == 'ordinary':
                needs, forbids = [family], []
            elif condition == 'legacy':
                needs, forbids = [], [family]
            else:
                needs = [family, *others] if profile == 'multi-clause' else [family, others[-1]]
                forbids = [others[0]] if profile == 'reverse-precedence' else []
            rows.append({'id': f'{seed}-{split}-{index:02d}', 'family': family,
                         'critical': condition == 'legacy' or bool(forbids),
                         'needs': needs, 'forbids': forbids})
        rng.shuffle(rows)
        cohorts[split] = rows
    return cohorts


def patches(prompt):
    return set() if prompt == BASE else set(prompt.split(','))


def score(prompt, row):
    enabled = patches(prompt)
    missing = [family for family in row['needs'] if f'broad_{family}' not in enabled and f'guarded_{family}' not in enabled]
    regressions = [family for family in row['forbids'] if f'broad_{family}' in enabled and f'guarded_{family}' not in enabled]
    misses = ' '.join(f'missing:{family}' for family in missing)
    regress = ' '.join(f'regression:{family}' for family in regressions)
    return Observation(not (missing or regressions), {'diagnosis': f'{misses} {regress}'.strip()})


def proposals(parent, feedback):
    missing = set(re.findall(r'missing:([a-z]+)', feedback)) & set(FAMILIES)
    regressions = set(re.findall(r'regression:([a-z]+)', feedback)) & set(FAMILIES)
    result = []
    for cautious in (False, True):
        candidate = patches(parent)
        for family in (missing | regressions):
            if cautious or family in regressions or f'guarded_{family}' in candidate:
                candidate.discard(f'broad_{family}')
                candidate.add(f'guarded_{family}')
            else:
                candidate.add(f'broad_{family}')
        result.append(','.join(sorted(candidate)) or BASE)
    return result


def run_gepa(train, validation, seed, evaluate, *, batched, enforce_reflections):
    from gepa.core.result import GEPAResult
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    prompts = []

    class CaptureState:
        state = None

        def on_iteration_end(self, event):
            self.state = event['state']

    capture = CaptureState()

    def reflect(request):
        if enforce_reflections and len(prompts) >= REFLECTION_LIMIT:
            raise RuntimeError('Reflection budget violation')
        _, parent, feedback = request.split('```', 2)
        proposed = proposals(parent.strip(), feedback)[len(prompts) % 2 if batched else 0]
        prompts.append(proposed)
        return f'```\n{proposed}\n```'

    def metric(prompt, example):
        result = evaluate(prompt, example)
        return float(result.passed), result.feedback

    proposal_rounds = REFLECTION_LIMIT // 2 if batched and enforce_reflections else REFLECTION_LIMIT
    config = GEPAConfig(engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
        max_metric_calls=METRIC_LIMIT, max_candidate_proposals=proposal_rounds, track_best_outputs=False,
        sampling_strategy=SameParentSampling(2) if batched else None),
        reflection=ReflectionConfig(reflection_lm=reflect, reflection_minibatch_size=MINIBATCH),
        stop_callbacks=ScoreThresholdStopper(1.0), callbacks=[capture])
    try:
        result = optimize_anything(seed_candidate=BASE, evaluator=metric, dataset=train, valset=validation,
            objective='Choose repair clauses that pass the recorded decisions and preserve the older behaviors.',
            config=config)
    except EvaluationLimitReached:
        if capture.state is None:
            raise
        result = GEPAResult.from_state(capture.state)
        candidate = result.best_candidate
        if not isinstance(candidate, dict) or len(candidate) != 1:
            raise ValueError('The benchmark requires GEPA to optimize a single prompt')
        return next(iter(candidate.values())), len(prompts), prompts, True
    return result.best_candidate, len(prompts), prompts, False


def compare(cases, seed, profiles, *, enforce_reflections):
    train, validation, holdout = (cases[name] for name in ('train', 'validation', 'holdout'))
    search_rows = {row['id']: row for row in [*train, *validation]}
    results = {}
    for name, width, race, adaptive in profiles:
        calls = []
        budget_stopped = False

        def evaluate(prompt, row):
            if row['id'] not in search_rows:
                raise RuntimeError('Search row violation')
            if len(calls) >= METRIC_LIMIT:
                raise EvaluationLimitReached
            observed = score(prompt, search_rows[row['id']])
            calls.append({'prompt': prompt, 'row': row['id'], 'passed': observed.passed})
            return observed

        if name in ('gepa', 'gepa-batched'):
            with redirect_stdout(StringIO()):
                prompt, reflections, events, budget_stopped = run_gepa(
                    train, validation, seed, evaluate, batched=name == 'gepa-batched',
                    enforce_reflections=enforce_reflections)
        else:
            def as_row(row):
                return Row(row['id'], row['family'], row['critical'])

            def evaluate_row(prompt, row):
                return evaluate(prompt, search_rows[row.id])

            def propose(parent, feedback, history, width):
                diagnosis = ' '.join(item.feedback['diagnosis'] for _, item in feedback)
                options = proposals(parent, diagnosis)
                if name == 'cpo-rewrite-first':
                    repair, rewrite = options
                    return ProposalPair(rewrite=rewrite, repair=repair)
                return options

            result = search(BASE, list(map(as_row, train)), list(map(as_row, validation)), evaluate_row,
                            propose, metric_limit=METRIC_LIMIT, rounds=REFLECTION_LIMIT, train_per_round=MINIBATCH,
                            proposals_per_round=width, seed=seed, race=race, adaptive=adaptive)
            prompt, reflections, events = result.prompt, result.reflections, result.events
            if result.evaluations != len(calls):
                raise RuntimeError('Optimizer and driver disagree on evaluation count')
        outcomes = {row['id']: score(prompt, row).passed for row in holdout}
        results[name] = {'prompt': prompt, 'passes': sum(outcomes.values()), 'evaluations': len(calls),
                         'reflections': reflections, 'criticalFailures': sum(row['critical'] and not outcomes[row['id']] for row in holdout),
                         'outcomes': outcomes, 'events': events, 'journal': calls, 'budgetStopped': budget_stopped}
    return results


def summary(results, contender, comparator):
    counts = Counter()
    for trial in results:
        baseline = trial['arms'][comparator]
        candidate = trial['arms'][contender]
        baseline_spend = baseline['evaluations'] + baseline['reflections']
        candidate_spend = candidate['evaluations'] + candidate['reflections']
        outcome = (candidate['passes'] - baseline['passes'], baseline['criticalFailures'] - candidate['criticalFailures'],
                   baseline_spend - candidate_spend)
        decision = 'tradeoff'
        if all(value == 0 for value in outcome):
            decision = 'tie'
        elif min(outcome) >= 0:
            decision = 'win'
        elif max(outcome) <= 0:
            decision = 'loss'
        counts[decision] += 1
    return dict(counts)


def compare_profiles(results, profiles, contender, comparator):
    groups = {}
    for profile in profiles:
        comparisons = []
        for trial in results:
            if trial['profile'] != profile:
                continue
            candidate, baseline = (trial['arms'][arm] for arm in (contender, comparator))
            critical_losses = sum(baseline['outcomes'][row_id] and not candidate['outcomes'][row_id]
                                  for row_id in trial['criticalHoldoutIDs'])
            costs = [result['evaluations'] + result['reflections'] for result in (candidate, baseline)]
            comparisons.append((candidate['passes'] - baseline['passes'], critical_losses, *costs))
        pass_delta, critical_losses, candidate_cost, baseline_cost = map(sum, zip(*comparisons))
        groups[profile] = {'exactPassDelta': pass_delta, 'matchedCriticalLosses': critical_losses,
                           'cpoSearchCalls': candidate_cost, 'baselineSearchCalls': baseline_cost}
    return groups


def qualifies(groups):
    for group in groups.values():
        delta = group['exactPassDelta']
        if group['matchedCriticalLosses'] or delta < 0:
            return False
        candidate_cost, baseline_cost = group['cpoSearchCalls'], group['baselineSearchCalls']
        if candidate_cost > baseline_cost or delta == 0 and 10 * candidate_cost > 9 * baseline_cost:
            return False
    return bool(groups)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--protocol', choices=('v2', 'cpo-v1', 'cpo-v2'), default='cpo-v2')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if version('gepa') != '0.1.4':
        raise SystemExit('The archived comparator is GEPA 0.1.4')
    arms = [('gepa', 1, False, False), ('gepa-batched', 2, False, False), ('frontier', 2, True, False),
            ('cpo', 2, True, True)]
    contender = 'cpo'
    controls = ('gepa', 'gepa-batched', 'frontier')
    profiles, seeds, dataset = {
        'v2': (PROFILES, SECOND_SEEDS, make_cases),
        'cpo-v1': (CPO_PROFILES, CPO_SEEDS, make_cpo_cases),
        'cpo-v2': (CPO_PROFILES, CPO_CONFIRMATION_SEEDS, make_cpo_cases),
    }[args.protocol]
    if args.protocol == 'cpo-v2':
        contender = 'cpo-rewrite-first'
        arms.append((contender, 2, True, True))
        controls += ('cpo',)
    runs = []
    for profile in profiles:
        for seed in seeds:
            cases = dataset(profile, seed)
            runs.append({'profile': profile, 'seed': seed, 'datasetSha256': digest(cases),
                         'holdoutRows': len(cases['holdout']),
                         'criticalHoldoutIDs': [row['id'] for row in cases['holdout'] if row['critical']],
                         'arms': compare(cases, seed, arms, enforce_reflections=True)})
    root = Path(__file__).resolve().parents[1]
    comparisons = {name: compare_profiles(runs, profiles, contender, name) for name in controls}
    gates = {name: qualifies(groups) for name, groups in comparisons.items()}
    report = {'protocol': f'frontier-synthetic-{args.protocol}', 'gepaVersion': '0.1.4',
              'maxMetricCalls': METRIC_LIMIT, 'maxReflections': REFLECTION_LIMIT,
              'summary': {name: summary(runs, contender, name) for name in controls},
              'comparisonsByProfile': comparisons, 'syntheticGate': gates,
              'qualifiesAgainstStockGEPA': all(gates[name] for name in ('gepa', 'gepa-batched')),
              'sourceSha256': {name: sha256((root / name).read_bytes()).hexdigest()
                               for name in ('benchmarks/frontier.py', 'cpo/optimizer.py', 'cpo/_contract.py')},
              'runs': runs}
    with args.out.open('x') as artifact:
        json.dump(report, artifact, sort_keys=True, separators=(',', ':'))
        artifact.write('\n')
    print(json.dumps({'summary': report['summary'], 'syntheticGate': gates}, sort_keys=True))


if __name__ == '__main__':
    main()
