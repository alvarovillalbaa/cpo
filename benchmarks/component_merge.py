"""Compare guarded three-way composition with GEPA's native merge operator."""

import argparse
from contextlib import redirect_stdout
from hashlib import sha256
from importlib.metadata import version
from io import StringIO
from itertools import combinations
import json
from pathlib import Path

from benchmarks import frontier, grounded
from cpo import Observation, Row, search
from cpo._contract import digest
from cpo.composition import merge_components


SEEDS = tuple(range(54601, 54829, 19))
PROFILES = (*frontier.CPO_PROFILES, 'component-interaction')
CAPS = (96, 144)
ARMS = ('cpo-ordinary', 'cpo-reserved', 'cpo-merge', 'gepa', 'gepa-native-merge')
ROUNDS = 6
MINIBATCH = 6


def encode(program):
    return json.dumps(program, sort_keys=True, separators=(',', ':'))


def cases(profile, seed):
    underlying = 'legacy-heavy' if profile == 'component-interaction' else profile
    return frontier.make_cpo_cases(underlying, seed)


def score(program, row, profile):
    if (profile == 'component-interaction' and row['critical'] and not row['needs']
            and program['aggregate'] != 'off' and program['precedence'] != 'off'):
        return Observation(False, {'diagnosis': 'The combined repairs conflict on this legacy case'})
    enabled = [f'{value}_{key}' for key, value in sorted(program.items()) if value != 'off']
    return frontier.score(','.join(enabled) or frontier.BASE, row)


def propose_edit(parent, slot, profile):
    family = frontier.FAMILIES[slot % len(frontier.FAMILIES)]
    update = parent.copy()
    if update[family] == 'off':
        update[family] = 'broad' if profile in ('legacy-heavy', 'component-interaction') and slot % 2 == 0 else 'guarded'
    elif update[family] == 'broad':
        update[family] = 'guarded'
    else:
        missing = next((key for key in frontier.FAMILIES if update[key] == 'off'), family)
        update[missing] = 'guarded'
    return update


def attempt_merge(result, row_ids, observe, search_log):
    """Try one fully funded merge of sibling candidates with complementary passes."""
    groups = {}
    scored = {}
    for event in result.events:
        if event['kind'] != 'validated':
            continue
        prompt = event['prompt']
        scored[prompt] = set(event['passed'])
        if 'parent' in event:
            groups.setdefault(event['parent'], []).append(prompt)
    champion = scored[result.prompt]
    options = []
    for parent, children in groups.items():
        for a, b in combinations(children, 2):
            if not (scored[a] - scored[b] and scored[b] - scored[a]):
                continue
            required = scored[a] | scored[b] | champion
            if required == champion:
                continue
            merged = merge_components(json.loads(parent), json.loads(a), json.loads(b))
            if merged is None:
                continue
            candidate = encode(merged)
            if candidate in scored:
                continue
            options.append((candidate, a, b, required))
    if not options:
        return result.prompt, None
    candidate, a, b, required = max(options, key=lambda option: len(option[3]))
    before = len(search_log)
    program = json.loads(candidate)
    passed = all(observe(program, row).passed for row in row_ids if row in required)
    if passed:
        for row in row_ids:
            if row not in required:
                observe(program, row)
    return (candidate if passed else result.prompt,
            {'candidate': candidate, 'parents': [a, b], 'preserved': passed, 'evaluations': len(search_log) - before})


def run_cpo(arm, groups, profile, seed, cap, initial, observe, search_log):
    reflected = []

    def propose(parent, _feedback, _history, width):
        options = []
        for _ in range(width):
            child = encode(propose_edit(json.loads(parent), len(reflected), profile))
            reflected.append(child)
            options.append(child)
        return options

    def rows(name):
        return [Row(row['id'], row['family'], row['critical']) for row in groups[name]]

    validation = rows('validation')
    allowance = cap if arm == 'cpo-ordinary' else cap - len(validation)
    result = search(encode(initial), rows('train'), validation,
                    lambda program, row: observe(json.loads(program), row.id), propose,
                    metric_limit=allowance, rounds=ROUNDS, train_per_round=MINIBATCH, seed=seed)
    if result.evaluations != len(search_log):
        raise ValueError('CPO search and the fixture journal disagree')
    chosen, attempt = result.prompt, None
    if arm == 'cpo-merge':
        chosen, attempt = attempt_merge(result, [row.id for row in validation], observe, search_log)
    return json.loads(chosen), reflected, ([] if attempt is None else [attempt]), result.prompt


class BudgetReached(Exception):
    """Stop the fixture before a full GEPA batch exceeds the physical cap."""


def run_gepa(arm, groups, profile, seed, cap, initial, observe):
    from gepa.core.result import GEPAResult
    from gepa.optimize_anything import EngineConfig, GEPAConfig, MergeConfig, ReflectionConfig, TrackingConfig
    from gepa.optimize_anything import optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    reflected, attempts = [], []

    class Capture:
        state = None

        def on_iteration_start(self, event):
            self.state = event['state']

        def on_merge_attempted(self, event):
            attempts.append({'candidate': encode(event['merged_candidate']), 'parents': list(event['parent_ids']),
                             'accepted': False})

        def on_merge_accepted(self, event):
            attempts[-1]['accepted'] = True

    capture = Capture()

    def evaluate(prompt, example):
        measured = observe(prompt, example['id'])
        return float(measured.passed), measured.feedback

    def propose(parent, _feedback, components):
        if set(components) != set(frontier.FAMILIES):
            raise ValueError('The fixture needs all named components')
        child = propose_edit(parent, len(reflected), profile)
        reflected.append(encode(child))
        return child

    config = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_metric_calls=cap, max_candidate_proposals=ROUNDS, track_best_outputs=False,
                            sampling_strategy=SameParentSampling(2)),
        reflection=ReflectionConfig(reflection_lm=None, custom_candidate_proposer=propose,
                                    reflection_minibatch_size=MINIBATCH, module_selector='all'),
        merge=MergeConfig(max_merge_invocations=1) if arm == 'gepa-native-merge' else None,
        tracking=TrackingConfig(logger=grounded.GepaLogger()), callbacks=[capture],
        stop_callbacks=ScoreThresholdStopper(1.0))
    with redirect_stdout(StringIO()):
        try:
            result = optimize_anything(initial, dataset=groups['train'], valset=groups['validation'],
                                       evaluator=evaluate, config=config)
        except BudgetReached:
            if capture.state is None:
                raise
            result = GEPAResult.from_state(capture.state)
    return result.best_candidate, reflected, attempts, None


def compare(profile, seed, cap):
    groups = cases(profile, seed)
    initial = dict.fromkeys(frontier.FAMILIES, 'off')
    search_rows = {row['id']: row for group in ('train', 'validation') for row in groups[group]}
    arms = {}
    for arm in ARMS:
        journal = {}

        def observe(program, row):
            key = encode(program), row
            if row not in search_rows:
                raise ValueError('Search accessed a holdout case')
            if key not in journal:
                if len(journal) >= cap:
                    raise BudgetReached
                journal[key] = score(program, search_rows[row], profile)
            return journal[key]

        if arm in ARMS[:3]:
            selected, proposals, merged, premerge = run_cpo(arm, groups, profile, seed, cap, initial, observe, journal)
        else:
            selected, proposals, merged, premerge = run_gepa(arm, groups, profile, seed, cap, initial, observe)
        outcomes = {row['id']: score(selected, row, profile).passed for row in groups['holdout']}
        arms[arm] = {'chosen': encode(selected), 'beforeMerge': premerge, 'outcomes': outcomes,
                     'evaluations': len(journal), 'reflectedSlots': len(proposals), 'merges': merged,
                     'searchSha256': digest([(prompt, row, value.passed) for (prompt, row), value in journal.items()])}
    if arms['cpo-reserved']['chosen'] != arms['cpo-merge']['beforeMerge']:
        raise ValueError('The guarded merge did not share the reserved search trajectory')
    return {'seed': seed, 'critical': [row['id'] for row in groups['holdout'] if row['critical']], 'arms': arms}


def summarize(trials):
    totals, comparisons = {}, {}
    for arm in ARMS:
        samples = [row['arms'][arm] for row in trials]
        totals[arm] = {'passes': sum(sum(item['outcomes'].values()) for item in samples),
                       'calls': sum(item['evaluations'] + item['reflectedSlots'] for item in samples),
                       'mergeAttempts': sum(len(item['merges']) for item in samples),
                       'mergesAccepted': sum(attempt.get('accepted', attempt.get('preserved', False))
                                             for item in samples for attempt in item['merges'])}
    for ref in (arm for arm in ARMS if arm != 'cpo-merge'):
        win, other = totals['cpo-merge'], totals[ref]
        losses = 0
        for trial in trials:
            current, control = (trial['arms'][arm]['outcomes'] for arm in ('cpo-merge', ref))
            losses += sum(control[row] and not current[row] for row in trial['critical'])
        gain, saved = win['passes'] - other['passes'], other['calls'] - win['calls']
        comparisons[ref] = {'passDelta': gain, 'callsSaved': saved, 'criticalLosses': losses,
                            'qualified': not losses and saved >= 0 and
                                         (gain > 0 or gain == 0 and 10 * saved >= other['calls'])}
    return {'totals': totals, 'comparisons': comparisons}


def prepare():
    root = Path(__file__).resolve().parents[1]
    files = ('benchmarks/component_merge.py', 'benchmarks/frontier.py', 'benchmarks/grounded.py',
             'cpo/__init__.py', 'cpo/_contract.py', 'cpo/optimizer.py', 'cpo/composition.py', 'requirements-benchmark.txt')
    return {'protocol': 'cpo-component-merge-v1', 'delivery': 'deterministic-fixture',
            'gepaVersion': '0.1.4', 'seeds': list(SEEDS), 'profiles': list(PROFILES), 'caps': list(CAPS),
            'arms': list(ARMS), 'proposalRounds': ROUNDS, 'reflectionMinibatch': MINIBATCH,
            'accounting': 'Each distinct search evaluation and scripted reflection slot counts once',
            'sourceSha256': {file: sha256((root / file).read_bytes()).hexdigest() for file in files},
            'cohortDigests': {profile: digest([cases(profile, seed) for seed in SEEDS]) for profile in PROFILES}}


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
    for cap in CAPS:
        results[str(cap)] = {}
        for profile in PROFILES:
            trials = [compare(profile, seed, cap) for seed in SEEDS]
            results[str(cap)][profile] = {**summarize(trials), 'trials': trials}
    report = {'plan': plan, 'planSha256': seal, 'results': results}
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, separators=(',', ':'))
        output.write('\n')


if __name__ == '__main__':
    main()
