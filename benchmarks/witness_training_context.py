"""Audit compact training blocks against errors restricted to specific contexts."""

import argparse
from collections import Counter
from hashlib import sha256
from itertools import combinations, product
import json
from pathlib import Path
from random import Random

from benchmarks import witness_training_discrimination as parent
from cpo._contract import digest


EPISODE, coverage, grounded = parent.EPISODE, parent.coverage, parent.grounded
REFERENCE = 'docs/witness-training-discrimination-results-v1.json'
REFERENCE_SHA256 = '2594bfdc36eff95ea99ad3f77e3e5a9dd465771eab5ac279437b9e1d6f07dd8c'
CHANNELS = ('chat', 'email', 'web')
CONTEXTS = {**coverage.REGIMES, 'ticket': tuple(product(coverage.TOPICS, CHANNELS))}
STRESS_SEED = 84310
NAMES = ('full', 'declaredFaults', 'factorPairs', 'completeContexts')


def context(task, row):
    regime = coverage.regime(task, row)
    if task == 'ticket':
        channel = coverage.grounded_fixture.facts(row['input'])['Channel']
        return (*regime, channel)
    return regime


def features(task, row, *, full):
    observed = context(task, row)
    prior = parent.signals(task, row)
    if full:
        return {*prior, f'context/{json.dumps(observed)}'}
    return prior | {f'pair/{left}/{right}/{json.dumps((observed[left], observed[right]))}'
                    for left, right in combinations(range(len(observed)), 2)}


def context_case(task, branch, index, rng):
    if task == 'ticket':
        topic, channel = branch
        index += (coverage.TOPICS.index(topic) - index) % len(coverage.TOPICS)
        inputs, expected, critical = coverage.policy.ticket(index, rng)
        chosen_channel = coverage.grounded_fixture.facts(inputs)['Channel']
        inputs = inputs.replace(f'Channel={chosen_channel}.', f'Channel={channel}.')
    else:
        generate = coverage.policy.warehouse if task == 'warehouse' else coverage.policy.outage
        inputs, expected, critical = generate(index, rng, branch)
    return index + 1, inputs, expected, critical


def stress_cases(groups):
    predecessors = (coverage.policy.cohorts(grounded.SEED), coverage.staged.cohorts())
    previous_stress = coverage.stress_cases(groups, predecessors)
    rng = Random(STRESS_SEED)
    panels = {}
    for task, branches in CONTEXTS.items():
        seen = {row['input'] for archive in (groups, *predecessors) for rows in archive[task].values() for row in rows}
        seen.update(row['input'] for row in previous_stress[task])
        rows = []
        index = 46_000
        for branch in branches:
            for _ in range(256):
                index, inputs, expected, critical = context_case(task, branch, index, rng)
                if inputs not in seen:
                    break
            else:
                raise ValueError('A fresh context stress case could not be generated')
            row = {'id': f'witness-training-context-{task}-{len(rows) + 1:02}', 'input': inputs,
                   'expected': expected, 'critical': critical}
            if context(task, row) != branch:
                raise ValueError('The new case differs from its declared context')
            rows.append(row)
            seen.add(inputs)
        panels[task] = rows
    return panels


def failures(task, rows):
    cases, critical = Counter(), Counter()
    for row in rows:
        expected = row['expected']
        changed = coverage.mutation(task, expected)
        if grounded.score(json.dumps(changed, sort_keys=True), expected)[0]:
            raise ValueError('The declared context fault must fail the exact grader')
        branch = context(task, row)
        cases[branch] += 1
        critical[branch] += int(row['critical'])
    return cases, critical


def measure(task, regions, stress, reference):
    prepared = []
    for index, published in enumerate(reference):
        offset = index * EPISODE.TRAIN_ROWS
        rows = regions['train'][offset:offset + EPISODE.TRAIN_ROWS]
        declared = parent.minimum_cover(rows, lambda row: parent.signals(task, row))
        if [row['id'] for row in declared] != published['minimumCover']['cases']:
            raise ValueError('The published compact training block changed')
        if parent.payload_size(task, declared) != published['minimumCover']['requestInputBytes']:
            raise ValueError('The published compressed reflection input changed')
        pairs = parent.minimum_cover(rows, lambda row: features(task, row, full=False))
        exact = parent.minimum_cover(rows, lambda row: features(task, row, full=True))
        prepared.append(dict(zip(NAMES, (rows, declared, pairs, exact), strict=True)))

    outcomes = {split: failures(task, rows) for split, rows in {
        'development': regions['holdout'], 'confirmation': regions['confirmation'], 'stress': stress}.items()}
    blocks = []
    for policies in prepared:
        full = {context(task, row) for row in policies['full']}
        output = {}
        for name, panel in policies.items():
            kept = {context(task, row) for row in panel}
            new_blind_spots = full - kept
            score = {split: {'lostCases': sum(cases[branch] for branch in new_blind_spots),
                             'lostCriticalCases': sum(critical[branch] for branch in new_blind_spots),
                             'casesUnresolvedInFullBlock': sum(count for branch, count in cases.items() if branch not in full)}
                     for split, (cases, critical) in outcomes.items()}
            output[name] = {'cases': [row['id'] for row in panel], 'requestInputBytes': parent.payload_size(task, panel),
                            'lostObservedContexts': sorted(new_blind_spots), 'scoring': score}
        blocks.append(output)
    return blocks


def prepare():
    groups, source = parent.prepare()
    raw = (EPISODE.ROOT / REFERENCE).read_bytes()
    reference = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA256 or reference['planSha256'] != digest(source):
        raise ValueError('Use the published training discrimination result')
    plan = {'protocol': 'witness-training-context-v1', 'parentPlanSha256': digest(source),
            'parentReceiptSha256': REFERENCE_SHA256, 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'trainingPolicies': NAMES, 'stressSeed': STRESS_SEED,
            'contexts': CONTEXTS, 'scope': 'Keep all original training distinctions, and compare additionally '
            'preserving every input factor pair or every full context observed within a training block.',
            'fault': 'In each declared context, change one exact output field and preserve all other contexts. '
            'Count scoring errors that the full training block could expose and the chosen subset could not.',
            'disjointStress': 'Construct one fresh fixture per context after the training policies are fixed. '
            'Neither the original scoring cases nor the supplemental cases select the training subset.'}
    return groups, plan, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    groups, plan, reference = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    stress = stress_cases(groups)
    tasks = {task: measure(task, regions, stress[task], reference['tasks'][task]) for task, regions in groups.items()}
    result = {'plan': plan, 'planSha256': seal, 'newProviderRequests': 0, 'tasks': tasks,
              'stressCases': {task: {'count': len(rows), 'sha256': digest(rows)} for task, rows in stress.items()}}
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
