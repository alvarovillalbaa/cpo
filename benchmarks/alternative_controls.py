"""Compare scored instruction history and instruction/example combinations offline."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from random import Random

from benchmarks import grounded, grounded_fixture as fixture, typed_policy
from cpo import Observation, ProposalPair, Row, search
from cpo._contract import digest


SEEDS = (42709, 42719, 42737)
BUDGETS = (40, 56)
ARMS = ('cpo-instruction', 'cpo-joint', 'gepa-joint', 'scored-history', 'instruction-demo-grid')
DEMO_COUNT = 4
REFLECTION_LIMIT = 6


def plan():
    root = Path(__file__).resolve().parents[1]
    paths = ('benchmarks/alternative_controls.py', 'benchmarks/grounded.py', 'benchmarks/grounded_fixture.py',
             'benchmarks/typed_policy.py', 'cpo/_contract.py', 'cpo/__init__.py', 'cpo/optimizer.py',
             'requirements-benchmark.txt')
    return {'protocol': 'typed-alternative-controls-v1', 'delivery': 'deterministic-fixture', 'arms': list(ARMS),
            'datasetSha256': {str(seed): digest(typed_policy.cohorts(seed)) for seed in SEEDS},
            'metricBudgets': list(BUDGETS), 'primaryBudget': BUDGETS[-1], 'reflectionLimit': REFLECTION_LIMIT,
            'gepaVersion': '0.1.4',
            'demosPerBundle': DEMO_COUNT, 'minimumPassesPerTaskPanel': 14,
            'minimumAdditionalPasses': 8, 'maxSearchCallPercentForEfficiency': 90,
            'sourceSha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in paths}}


def encode(instruction, demos=()):
    return json.dumps({'instruction': instruction, 'demos': list(demos)}, sort_keys=True)


def demo_features(task, facts):
    if task == 'ticket':
        return {'queue': facts['Topic']}
    if task == 'warehouse':
        return {'owner': facts['Site'], 'windowHours': facts['Tier']}
    return {'review': (facts['Evidence'], int(facts['Duration minutes']) >= 120),
            'reason': (facts['Evidence'], int(facts['Duration minutes']) >= 120)}


def complete(task, program, inputs, training):
    """Apply trained literals only to fields left open by the instruction."""
    prompt = grounded.load_json(program)
    instruction = prompt['instruction']
    base = fixture.resolve(task, instruction, inputs)
    fields = set() if instruction == grounded.BASELINE else set(grounded.load_json(instruction)['fields'])
    target = demo_features(task, fixture.facts(inputs))
    examples = [(demo_features(task, fixture.facts(training[index]['input'])), training[index]['expected'])
                for index in prompt['demos']]
    for key, signature in target.items():
        if key in fields:
            continue
        votes = {expected[key] for features, expected in examples if features[key] == signature}
        if len(votes) == 1:
            base[key], = votes
    return json.dumps(base, sort_keys=True)


def scored_history(initial, opening, validation, evaluate, reflect, cap):
    """Fully grade each instruction and present the score history in ascending order."""
    scores = {}
    pending = iter(opening)
    for _ in range(cap // len(validation)):
        prompt = next(pending, None)
        if prompt is None:
            history = sorted(scores.items(), key=lambda entry: entry[1])
            parent = history[-1][0]
            prompt = reflect(parent, [
                {'instruction': grounded.load_json(candidate)['instruction'], 'exact': exact, 'fields': fields}
                for candidate, (exact, fields) in history
            ])
            if prompt in scores:
                break
        scores[prompt] = trial_score(prompt, validation, evaluate)
        if scores[prompt][0] == len(validation):
            break
    return max(scores, key=scores.get, default=initial)


def trial_score(program, validation, evaluate):
    receipts = [evaluate(program, row) for row in validation]
    return sum(observation.passed for observation in receipts), sum(observation.matched_fields for observation in receipts)


def grid(initial, options, demos, validation, evaluate, cap):
    """Evaluate instruction and demonstration combinations in a fixed order."""
    candidates = (initial, *(encode(instruction, bundle) for bundle in (demos, ()) for instruction in options))
    best, score = initial, (-1, -1)
    for program in candidates[:cap // len(validation)]:
        measured = trial_score(program, validation, evaluate)
        if measured > score:
            best, score = program, measured
        if measured[0] == len(validation):
            break
    return best


def cpo(initial, bank, groups, evaluate, reflect, *, seed, cap, demos):
    rows = {row['id']: row for cohort in ('train', 'validation') for row in groups[cohort]}
    opening = True

    def vector(cohort):
        return [Row(row['id'], 'typed', row['critical'], len(row['expected'])) for row in groups[cohort]]

    def propose(parent, feedback, history, _width):
        nonlocal opening
        if opening:
            opening = False
            return ProposalPair(encode(bank[0], demos), encode(bank[1], demos))
        candidate = reflect(parent, [observation.feedback for _, observation in feedback])
        if not demos:
            return (candidate,)
        instruction = grounded.load_json(candidate)['instruction']
        return ProposalPair(encode(instruction, demos), encode(instruction))

    result = search(initial, vector('train'), vector('validation'), lambda program, row: evaluate(program, rows[row.id]),
                    propose, metric_limit=cap, rounds=REFLECTION_LIMIT, train_per_round=grounded.MINIBATCH,
                    seed=seed, adaptive=True, field_credit=True)
    return result.prompt


def gepa(initial, bank, groups, evaluate, reflect, *, seed, cap, demos):
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.utils.stop_condition import ScoreThresholdStopper

    train, validation = groups['train'], groups['validation']
    fields = len(train[0]['expected'])
    # A single exact match takes precedence over all partial field credit in either cohort.
    weight = 1 << (max(len(train), len(validation)) * fields).bit_length()
    opening = iter(encode(instruction, demos) for instruction in bank)
    observations = 0

    def grade(prompt, example):
        nonlocal observations
        observations += 1
        receipt = evaluate(prompt, example)
        return ((int(receipt.passed) * weight + receipt.matched_fields) / (weight + fields), receipt.feedback)

    def propose(candidate, feedback, components):
        component, = components
        parent = candidate[component]
        prompt = next(opening, None) if parent == initial else None
        return {component: prompt if prompt is not None else reflect(parent, feedback)}

    minibatch = grounded.MINIBATCH
    settings = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_metric_calls=cap, max_candidate_proposals=REFLECTION_LIMIT, track_best_outputs=False),
        reflection=ReflectionConfig(reflection_lm=None, custom_candidate_proposer=propose,
                                    reflection_minibatch_size=minibatch),
        tracking=TrackingConfig(logger=grounded.GepaLogger()),
        stop_callbacks=[ScoreThresholdStopper(1.0),
                        lambda _: observations + 2 * minibatch + len(validation) > cap],
    )
    return optimize_anything(initial, evaluator=grade, dataset=train, valset=validation,
                             config=settings).best_candidate


def compare(task, groups, seed, cap):
    training, validation = groups['train'], groups['validation']
    selectable = {row['id'] for row in (*training, *validation)}
    demos = tuple(sorted(Random(seed).sample(range(len(training)), DEMO_COUNT)))
    opening = {'task': task, 'role': 'reflection', 'instruction': grounded.OPENING,
               'input': {'current': grounded.BASELINE, 'labeledTraining': training}}
    bank = grounded.proposals(fixture.respond(opening), grounded.BASELINE, ('rewrite', 'repair'))
    initial = encode(grounded.BASELINE)
    results, choices = {}, {}
    for arm in ARMS:
        counts = Counter(reflections=1)
        observed = {}
        reflection_trace = []

        def evaluate(program, row):
            if row['id'] not in selectable:
                raise ValueError('Search case violation')
            key = (program, row['id'])
            if key not in observed:
                if counts['evaluations'] >= cap:
                    raise ValueError('Search budget violation')
                counts['evaluations'] += 1
                raw = complete(task, program, row['input'], training)
                passed, fields = grounded.score(raw, row['expected'])
                observed[key] = Observation(passed, {'id': row['id'], 'observed': raw}, fields)
            return observed[key]

        def reflect(parent, context):
            if counts['reflections'] >= REFLECTION_LIMIT:
                raise ValueError('Reflection budget violation')
            counts['reflections'] += 1
            instruction = grounded.load_json(parent)['instruction']
            request = {'task': task, 'role': 'reflection', 'instruction': grounded.UPDATE,
                       'input': {'current': instruction, 'labeledTraining': training,
                                 'candidateHistory' if arm == 'scored-history' else 'recentFeedback': context}}
            response = fixture.respond(request)
            reflection_trace.append((digest(request), digest(response)))
            updated = grounded.load_json(response)['instruction']
            return encode(updated, grounded.load_json(parent)['demos'])

        if arm.startswith('cpo-'):
            picked = cpo(initial, bank, groups, evaluate, reflect, seed=seed, cap=cap,
                         demos=demos if arm == 'cpo-joint' else ())
        elif arm == 'gepa-joint':
            picked = gepa(initial, bank, groups, evaluate, reflect, seed=seed, cap=cap, demos=demos)
        elif arm == 'scored-history':
            picked = scored_history(initial, (initial, *map(encode, bank)), validation, evaluate, reflect, cap)
        else:
            picked = grid(initial, bank, demos, validation, evaluate, cap)
        choices[arm] = picked
        results[arm] = {**counts, 'evaluations': counts['evaluations'], 'prompt': grounded.load_json(picked),
                        'searchSha256': digest([(prompt, row, value.passed, value.matched_fields)
                                               for (prompt, row), value in observed.items()]),
                        'reflectionSha256': digest(reflection_trace)}

    for row in groups['holdout']:
        replies = {prompt: complete(task, prompt, row['input'], training) for prompt in set(choices.values())}
        for arm, prompt in choices.items():
            exact, _ = grounded.score(replies[prompt], row['expected'])
            results[arm].setdefault('holdout', {})[row['id']] = exact
    return {'seed': seed, 'task': task, 'cap': cap, 'trainingDemoIDs': [training[index]['id'] for index in demos],
            'criticalHoldoutIDs': [row['id'] for row in groups['holdout'] if row['critical']], 'arms': results}


def summarize(trials, frozen):
    def passes(entry):
        return sum(entry['holdout'].values())

    totals = {arm: {'exact': sum(passes(trial['arms'][arm]) for trial in trials),
                    'searchCalls': sum(trial['arms'][arm]['evaluations'] + trial['arms'][arm]['reflections']
                                       for trial in trials)} for arm in ARMS}
    joint = 'cpo-joint'
    paired = {}
    for reference in (arm for arm in ARMS if arm != joint):
        gaps = [passes(trial['arms'][joint]) - passes(trial['arms'][reference]) for trial in trials]
        critical = sum(trial['arms'][reference]['holdout'][case] and not trial['arms'][joint]['holdout'][case]
                       for trial in trials for case in trial['criticalHoldoutIDs'])
        saving = totals[reference]['searchCalls'] - totals[joint]['searchCalls']
        quality = sum(gaps) >= frozen['minimumAdditionalPasses'] and saving >= 0
        efficiency = (100 * totals[joint]['searchCalls'] <=
                      frozen['maxSearchCallPercentForEfficiency'] * totals[reference]['searchCalls'])
        floor = all(passes(trial['arms'][joint]) >= frozen['minimumPassesPerTaskPanel'] for trial in trials)
        paired[reference] = {'addedPasses': sum(gaps), 'criticalLosses': critical, 'searchCallsSaved': saving,
                             'panelsWithLoss': sum(gap < 0 for gap in gaps),
                             'qualified': floor and not critical and min(gaps) >= 0 and (quality or efficiency)}
    return {'totals': totals, 'comparisons': paired, 'qualified': all(item['qualified'] for item in paired.values())}


def report():
    frozen = plan()
    try:
        if version('gepa') != frozen['gepaVersion']:
            raise ValueError('Install the pinned GEPA benchmark dependency')
    except PackageNotFoundError as error:
        raise ValueError('Install the pinned GEPA benchmark dependency') from error
    tasks = [(seed, task, groups) for seed in SEEDS for task, groups in typed_policy.cohorts(seed).items()]
    results = {}
    for cap in BUDGETS:
        trials = [compare(task, groups, seed, cap) for seed, task, groups in tasks]
        results[str(cap)] = {'trials': trials, **summarize(trials, frozen)}
    return {'plan': frozen, 'planSha256': digest(frozen), 'budgets': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--out', type=Path)
    mode.add_argument('--replay', type=Path)
    args = parser.parse_args()
    if not (args.out or args.replay):
        frozen = plan()
        print(json.dumps({**frozen, 'planSha256': digest(frozen)}, indent=2, sort_keys=True))
        return
    if args.out and args.out.exists():
        parser.error('Fixture execution requires a fresh output path')
    data = report()
    if args.replay:
        if grounded.load_json(args.replay.read_bytes()) != data:
            parser.error('Artifact differs from the fixture replay')
    else:
        with args.out.open('x') as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write('\n')
    labels = ('totals', 'comparisons', 'qualified')
    print(json.dumps({cap: {name: summary[name] for name in labels} for cap, summary in data['budgets'].items()},
                     indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
