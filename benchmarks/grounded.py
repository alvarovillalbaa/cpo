"""Run or replay a provider-neutral comparison on the published policy cohorts."""

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import logging
from pathlib import Path
from random import Random

from benchmarks.typed_policy import SPLITS, TASKS, cohorts
from cpo import Observation, ProposalPair, Row, optimizer
from cpo._contract import classification, digest, unique_object


SEED = 41491
ARMS = ('cpo', 'gepa-repair-first', 'gepa-batched', 'gepa-rewrite-first')
CONTROLS = ARMS[1:]
METRIC_LIMIT = 56
REFLECTION_LIMIT = 6
MINIBATCH = 2
REPEATS = 2
BASELINE = 'Use the legacy default policy. Return one JSON object of the required shape.'
EVIDENCE = ('Derive reusable policy rules from labeledTraining. Preserve exact canonical output values '
            'and the JSON object contract. Use recentFeedback to diagnose mistakes and candidateHistory '
            'for aggregate search context when present. Avoid copying record identities.')
OPENING = EVIDENCE + ' Return a JSON object with two distinct standalone strings named rewrite and repair.'
UPDATE = EVIDENCE + ' Return a JSON object with one standalone string named instruction.'


class ResponderFailed(BaseException):
    """End the comparison after a failed response call."""


class GepaLogger:
    def log(self, message):
        logging.getLogger(__name__).debug(message)


def load_json(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def plan():
    root = Path(__file__).resolve().parents[1]
    filenames = ('benchmarks/grounded.py', 'benchmarks/typed_policy.py', 'benchmarks/grounded_fixture.py',
                 'cpo/optimizer.py', 'cpo/_contract.py', 'requirements-benchmark.txt')
    return {'protocol': 'portable-grounded-v1', 'seed': SEED, 'arms': list(ARMS),
            'datasetSha256': digest(cohorts(SEED)), 'splitSizes': SPLITS, 'gepaVersion': '0.1.4',
            'metricLimitPerTaskAndArm': METRIC_LIMIT, 'reflectionLimitPerTaskAndArm': REFLECTION_LIMIT,
            'holdoutRepeats': REPEATS, 'holdoutMinimumPerTask': 27, 'minimumAdditionalPasses': 8,
            'maximumSearchCallPercentForEfficiency': 90,
            'sourceSha256': {name: sha256((root / name).read_bytes()).hexdigest() for name in filenames}}


def proposals(text, parent, keys):
    try:
        value = load_json(text)
    except ValueError:
        return ()
    if (not isinstance(value, dict) or set(value) != set(keys) or
            any(not isinstance(item, str) for item in value.values())):
        return ()
    prompts = tuple(value[key].strip() for key in keys)
    if len(set(prompts)) != len(prompts) or any(
        not item or item == parent or len(item.encode()) > 1600 for item in prompts
    ):
        return ()
    return prompts


def score(text, expected):
    decision = classification(text, expected)
    matched = 0
    if decision == 'pass':
        matched = len(expected)
    elif decision == 'wrong_values':
        observed = load_json(text)
        matched = sum(observed[key] == value for key, value in expected.items())
    return decision == 'pass', matched


def choose_cpo(task, train, validation, bank, evaluate, reflect):
    data = {row['id']: row for row in (*train, *validation)}
    opening = True

    def evaluate_row(prompt, row):
        passed, matched, text = evaluate(prompt, data[row.id])
        return Observation(passed, {'id': row.id, 'observed': text}, matched)

    def propose(parent, feedback, history, _width):
        nonlocal opening
        if opening:
            opening = False
            return ProposalPair(*bank)
        return reflect(parent, [observation.feedback for _, observation in feedback],
                       [{'instructionExcerpt': prompt[:256], 'validationPassesByFamily': counts}
                        for prompt, counts in history])

    def examples(rows):
        return [Row(row['id'], task, row['critical'], len(row['expected'])) for row in rows]

    return optimizer.search(BASELINE, examples(train), examples(validation), evaluate_row, propose,
                            metric_limit=METRIC_LIMIT, rounds=REFLECTION_LIMIT, train_per_round=MINIBATCH,
                            seed=SEED, adaptive=True, field_credit=True).prompt


def choose_gepa(arm, train, validation, bank, evaluate, reflect):
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    width = 2 if arm == 'gepa-batched' else 1
    allowed = {row['id']: row for row in (*train, *validation)}
    opening = iter(bank if arm == 'gepa-rewrite-first' else reversed(bank))
    observations = 0

    def metric(prompt, example):
        nonlocal observations
        if allowed.get(example['id']) != example:
            raise ValueError('GEPA evaluated a case outside search')
        observations += 1
        passed, _, text = evaluate(prompt, example)
        return float(passed), {'id': example['id'], 'observed': text}

    def proposal(candidate, feedback, components):
        component, = components
        parent = candidate[component]
        suggestion = next(opening, None) if parent == BASELINE else None
        return {component: suggestion or next(iter(reflect(parent, feedback, [])), parent)}

    config = GEPAConfig(
        engine=EngineConfig(seed=SEED, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_metric_calls=METRIC_LIMIT, max_candidate_proposals=REFLECTION_LIMIT // width,
                            track_best_outputs=False, sampling_strategy=SameParentSampling(width) if width > 1 else None),
        reflection=ReflectionConfig(reflection_lm=None, custom_candidate_proposer=proposal,
                                    reflection_minibatch_size=MINIBATCH),
        tracking=TrackingConfig(logger=GepaLogger()),
        stop_callbacks=[ScoreThresholdStopper(1.0),
                        lambda _: observations + width * (2 * MINIBATCH + len(validation)) > METRIC_LIMIT],
    )
    return optimize_anything(BASELINE, evaluator=metric, dataset=train, valset=validation,
                             config=config).best_candidate


def search_task(task, rows, dispatch):
    train, validation = rows['train'], rows['validation']
    training = [{key: row[key] for key in ('id', 'input', 'expected')} for row in train]

    def reflection(arm, parent, recent, history, *, opening=False):
        request = {'task': task, 'current': parent, 'labeledTraining': training,
                   'recentFeedback': recent, 'candidateHistory': history}
        text = dispatch(arm, 'reflection', OPENING if opening else UPDATE, request)
        return proposals(text, parent, ('rewrite', 'repair') if opening else ('instruction',))

    bank = reflection('shared', BASELINE, [], [], opening=True)
    if not bank:
        raise ValueError('Shared opening requires a valid rewrite and repair')
    result = {'initial': BASELINE}
    order = list(ARMS)
    Random(f'{SEED}:{task}').shuffle(order)
    for arm in order:
        def evaluate(prompt, row):
            text = dispatch(arm, 'evaluation', prompt, row['input'])
            passed, matched = score(text, row['expected'])
            return passed, matched, text

        def reflect(parent, feedback, history):
            return reflection(arm, parent, feedback, history)

        result[arm] = (choose_cpo(task, train, validation, bank, evaluate, reflect) if arm == 'cpo' else
                       choose_gepa(arm, train, validation, bank, evaluate, reflect))
    return result


def qualify_task(task, holdout, selected, dispatch):
    order = Random(f'{SEED}:{task}:holds')
    outcomes = {}
    for case in holdout:
        for repeat in range(REPEATS):
            arms = list(selected)
            order.shuffle(arms)
            groups = defaultdict(list)
            for arm in arms:
                groups[selected[arm]].append(arm)
            matches = {}
            for prompt, matched_arms in groups.items():
                text = dispatch('paired', 'qualification', prompt, case['input'], repeat=repeat)
                passed, _ = score(text, case['expected'])
                matches.update(dict.fromkeys(matched_arms, passed))
            outcomes[(case['id'], repeat)] = (case['critical'], matches)
    return outcomes


def verdict(outcomes, costs, frozen):
    scores = {arm: {task: sum(passes[arm] for _, passes in cases.values()) for task, cases in outcomes.items()}
              for arm in ('initial', *ARMS)}
    comparisons = {}
    for arm in ('initial', *CONTROLS):
        deltas, critical_losses = Counter(), 0
        for cases in outcomes.values():
            for (case, _), (critical, passes) in cases.items():
                difference = int(passes['cpo']) - int(passes[arm])
                deltas[case] += difference
                critical_losses += critical and difference < 0
        gain = sum(deltas.values())
        preserves = not critical_losses and all(scores['cpo'][task] >= score for task, score in scores[arm].items())
        qualifies = preserves
        if arm != 'initial':
            efficient = (min(deltas.values()) >= 0 and
                         costs['cpo'] * 100 <= costs[arm] * frozen['maximumSearchCallPercentForEfficiency'])
            qualifies = preserves and (gain >= frozen['minimumAdditionalPasses'] or efficient)
        comparisons[arm] = {'addedPasses': gain, 'criticalLosses': critical_losses, 'qualified': qualifies}
    return {'passesByTask': scores, 'comparisons': comparisons,
            'qualified': all(value >= frozen['holdoutMinimumPerTask'] for value in scores['cpo'].values())
            and all(entry['qualified'] for entry in comparisons.values())}


def run(respond, *, delivery):
    """Use a caller-supplied responder accepting one request dict and returning text."""
    frozen = plan()
    try:
        if version('gepa') != frozen['gepaVersion']:
            raise ValueError('Install the pinned GEPA benchmark dependency')
    except PackageNotFoundError as error:
        raise ValueError('Install the pinned GEPA benchmark dependency') from error
    if delivery not in ('fixture', 'model'):
        raise ValueError('Declare fixture or model delivery')
    groups = cohorts(SEED)
    journal, counts, costs = [], Counter(), Counter()
    selections, outcomes = {}, {}
    types = {str: 'string', int: 'integer', bool: 'boolean'}
    schemas = {}
    for task, task_groups in groups.items():
        example = task_groups['train'][0]['expected']
        schemas[task] = {'type': 'object', 'properties': {field: {'type': types[type(value)]}
                                                       for field, value in example.items()},
                         'required': list(example), 'additionalProperties': False}

    def dispatch(task, arm, role, instruction, inputs, *, repeat=None):
        key = task, arm, role
        limit = (METRIC_LIMIT if role == 'evaluation' else
                 1 if arm == 'shared' else REFLECTION_LIMIT if role == 'reflection' else
                 SPLITS['holdout'] * REPEATS * (len(ARMS) + 1))
        if counts[key] >= limit:
            raise ValueError(f'{task} {arm} exhausted its {role} limit')
        payload = {'task': task, 'role': role, 'instruction': instruction, 'input': inputs}
        if role != 'reflection':
            payload['jsonSchema'] = schemas[task]
        if repeat is not None:
            payload['repeat'] = repeat
        counts[key] += 1
        if role != 'qualification':
            costs[arm] += 1
        try:
            text = respond(deepcopy(payload))
            if not isinstance(text, str):
                raise ValueError('A responder must return text')
        except Exception as error:
            raise ResponderFailed from error
        journal.append({'arm': arm, 'request': payload, 'response': text})
        return text

    try:
        for task in TASKS:
            selections[task] = search_task(task, groups[task], lambda *args: dispatch(task, *args))
        for task in TASKS:
            outcomes[task] = qualify_task(task, groups[task]['holdout'], selections[task],
                                         lambda *args, **kwargs: dispatch(task, *args, **kwargs))
    except ResponderFailed as error:
        raise error.__cause__ from None
    attributable = {arm: costs[arm] + costs['shared'] for arm in ARMS}
    return {'plan': frozen, 'planSha256': digest(frozen), 'delivery': delivery, 'journal': journal,
            'selected': selections, 'searchCallsByArm': attributable,
            'physicalSearchCalls': sum(costs.values()), 'outcome': verdict(outcomes, attributable, frozen)}


def replay(artifact):
    frozen = plan()
    if artifact['plan'] != frozen or artifact['planSha256'] != digest(frozen):
        raise ValueError('Grounded report does not match this benchmark revision')
    pending = iter(artifact['journal'])

    def respond(request):
        entry = next(pending, None)
        if entry is None or entry['request'] != request:
            raise ValueError('Grounded journal request differs from replay')
        return entry['response']

    result = run(respond, delivery=artifact['delivery'])
    if next(pending, None) is not None or result != artifact:
        raise ValueError('Grounded report differs from the replayed outcome')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--fixture', action='store_true')
    actions.add_argument('--replay', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if bool(args.out) != args.fixture or (args.out and args.out.exists()):
        parser.error('Fixture execution requires a fresh --out path')
    if args.fixture:
        from benchmarks.grounded_fixture import respond

        result = run(respond, delivery='fixture')
        with args.out.open('x') as report:
            json.dump(result, report, sort_keys=True, indent=2)
            report.write('\n')
        result = {'delivery': result['delivery'], **result['outcome']}
    elif args.replay:
        result = replay(load_json(args.replay.read_bytes()))['outcome']
    else:
        frozen = plan()
        result = {**frozen, 'planSha256': digest(frozen)}
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
