"""Exercise bounded opening recovery through CPO and official GEPA with scripted replies."""

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import grounded, grounded_fixture
from cpo import Observation, ProposalBatch, Row, search
from cpo._contract import digest
from cpo.opening import OpeningReply, collect_opening


ROOT = Path(__file__).resolve().parents[1]
MODES = ('pair', 'split', 'fill-missing')
PROFILES = {
    'complete': (),
    'joint-cap': ('pair',),
    'joint-and-repair-cap': ('pair', 'repair'),
    'all-opening-capped': ('pair', 'rewrite', 'repair'),
}
SINGLE = {role: grounded.EVIDENCE + f' Produce only the {role}. Return one JSON string field named instruction.'
          for role in ('rewrite', 'repair')}


def plan():
    parent = grounded.plan()
    paths = ('benchmarks/opening_budget.py', 'cpo/opening.py', *parent['sourceSha256'])
    return {'protocol': 'cpo-opening-budget-fixture-v1', 'priorPlanSha256': digest(parent),
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'modes': MODES, 'profiles': PROFILES, 'gepaVersion': parent['gepaVersion'],
            'pairTokens': 1200, 'singleTokens': 1200, 'openingOutputBudget': 3600, 'instructionBytes': 1600}


def choose_cpo(task, train, validation, bank, evaluate, reflect):
    data = {row['id']: row for row in (*train, *validation)}
    opening = bank

    def observe(prompt, row):
        passed, matched, text = evaluate(prompt, data[row.id])
        return Observation(passed, {'id': row.id, 'observed': text}, matched)

    def propose(parent, feedback, history, _width):
        nonlocal opening
        if opening:
            batch, opening = opening, ()
            return ProposalBatch(batch)
        return reflect(parent, [item.feedback for _, item in feedback],
                       [{'instructionExcerpt': prompt[:256], 'validationPassesByFamily': counts}
                        for prompt, counts in history])

    def cohort(rows):
        return [Row(row['id'], task, row['critical'], len(row['expected'])) for row in rows]

    return search(grounded.BASELINE, cohort(train), cohort(validation),
                  observe, propose, metric_limit=grounded.METRIC_LIMIT, rounds=grounded.REFLECTION_LIMIT,
                  train_per_round=grounded.MINIBATCH, seed=grounded.SEED, adaptive=True, field_credit=True).prompt


def run(settings, mode, capped):
    groups = grounded.cohorts(grounded.SEED)
    journal, limits, costs = [], Counter(), Counter()
    banks, selected, outcomes = {}, {}, {}

    def dispatch(task, arm, role, instruction, inputs, *, repeat=None, cap=None):
        key = task, arm, role
        limits[key] += 1
        resource = {'evaluation': grounded.METRIC_LIMIT, 'reflection': grounded.REFLECTION_LIMIT}
        if arm != 'shared' and role in resource and limits[key] > resource[role]:
            raise ValueError('An arm exceeded the original search allowance')
        reply = grounded_fixture.respond({'task': task, 'role': role, 'instruction': instruction, 'input': inputs})
        if role != 'qualification':
            costs[arm] += 1
        journal.append((task, arm, role, instruction, inputs, repeat, cap, reply))
        return reply

    for task, rows in groups.items():
        training = [{key: row[key] for key in ('id', 'input', 'expected')} for row in rows['train']]
        initial = grounded.BASELINE

        def context(parent, recent, history):
            return {'task': task, 'current': parent, 'labeledTraining': training,
                    'recentFeedback': recent, 'candidateHistory': history}

        def request(role, cap):
            inputs = context(initial, [], [])
            if task == 'outage' and role in capped:
                costs['shared'] += 1
                journal.append((task, 'shared', role, inputs, cap, 'output_limit'))
                return OpeningReply('output_limit', '')
            # The fixture uses the same matched rewrite and repair templates
            # regardless of how many slots the request asks it to return.
            bank = grounded_fixture.respond({'task': task, 'role': 'reflection', 'instruction': grounded.OPENING,
                                             'input': inputs})
            if role != 'pair':
                bank = json.dumps({'instruction': json.loads(bank)[role]}, sort_keys=True)
            costs['shared'] += 1
            journal.append((task, 'shared', role, grounded.OPENING if role == 'pair' else SINGLE[role], inputs, cap, bank))
            return OpeningReply('completed', bank)

        opening = collect_opening(initial, request, mode=mode, pair_tokens=settings['pairTokens'],
                                  single_tokens=settings['singleTokens'], output_budget=settings['openingOutputBudget'],
                                  max_instruction_bytes=settings['instructionBytes'])
        banks[task] = [asdict(attempt) for attempt in opening.attempts]
        if mode == 'pair' and len(opening.prompts) != 2:
            break
        selected[task] = {'initial': initial}
        order = list(grounded.ARMS)
        Random(f'{grounded.SEED}:{task}').shuffle(order)
        for arm in order:
            def evaluate(prompt, row):
                text = dispatch(task, arm, 'evaluation', prompt, row['input'])
                exact, matched = grounded.score(text, row['expected'])
                return exact, matched, text

            def reflect(parent, recent, history):
                text = dispatch(task, arm, 'reflection', grounded.UPDATE, context(parent, recent, history))
                return grounded.proposals(text, parent, ('instruction',))

            train, validation = rows['train'], rows['validation']
            selection = (choose_cpo(task, train, validation, opening.prompts, evaluate, reflect) if arm == 'cpo' else
                         grounded.choose_gepa(arm, train, validation, opening.prompts, evaluate, reflect))
            selected[task][arm] = selection

    if len(selected) == len(groups):
        for task, rows in groups.items():
            outcomes[task] = grounded.qualify_task(
                task, rows['holdout'], selected[task],
                lambda *args, **kwargs: dispatch(task, *args, **kwargs),
            )
    attributable = {arm: costs[arm] + costs['shared'] for arm in grounded.ARMS}
    return {'status': 'completed' if outcomes else 'aborted-at-opening', 'openings': banks,
            'physicalSearchCalls': sum(costs.values()), 'searchCallsByArm': attributable,
            'physicalQualificationCalls': len(journal) - sum(costs.values()),
            'selectedSha256': digest(selected), 'journalSha256': digest(journal),
            'outcome': grounded.verdict(outcomes, attributable, grounded.plan()) if outcomes else None}


def replay(settings):
    results = {profile: {mode: run(settings, mode, faults) for mode in settings['modes']}
               for profile, faults in settings['profiles'].items()}
    baseline = grounded.run(grounded_fixture.respond, delivery='fixture')
    original = results['complete']['pair']
    if (original['selectedSha256'] != digest(baseline['selected'])
            or original['physicalSearchCalls'] != baseline['physicalSearchCalls']
            or original['physicalQualificationCalls'] != len(baseline['journal']) - baseline['physicalSearchCalls']
            or original['searchCallsByArm'] != baseline['searchCallsByArm']
            or original['outcome'] != baseline['outcome']):
        raise ValueError('The intact pair no longer reproduces the original fixture')
    return {'plan': settings, 'planSha256': digest(settings), 'delivery': 'fixture', 'results': results}


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
    if version('gepa') != settings['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(settings)
    with args.out.open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
