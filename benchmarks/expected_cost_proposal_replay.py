"""Replay proposal-driven CPO through the exact expected-cost cycle API."""

import argparse
from collections import Counter, deque
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import grounded, grounded_fixture, prompteval_continuous as continuous
from benchmarks.case_difficulty_allocation import checked_file
from benchmarks.four_case_qualification_transfer import interval
from cpo import Observation, ProposalBatch, ProposalPair, Row, run_cycle
from cpo._contract import digest
from cpo.expected_cost_proposal_cycle import run_expected_cost_proposal_cycle
from cpo.paired_qualification import certify_paired_qualification


ROOT = Path(__file__).resolve().parents[1]
PHASES = ('development', 'retrospective-transfer')
SOURCE = '430e4f3503396963223aeefb1aabeb6c98387da10d8755f8bc810e128833d26c'
CAPS = (72, 88, 104, 128, 171)
BOOTSTRAP = {'draws': 4096, 'seed': 20261201}
RULES = ('full', 'seeded', 'expected')


def prepare():
    source = checked_file('docs/prompteval-continuous-results-v1.json', SOURCE)
    phases = {}
    for phase in PHASES:
        plan, snapshot = continuous.prepare(phase)
        if digest(plan) != source[phase]['planSha256'] or plan['evaluationLookupLimit'] != CAPS[-1]:
            raise ValueError(f'The original proposal-driven comparison changed for {phase}')
        phases[phase] = plan, snapshot['panels'], source[phase]['panels']
    paths = ('benchmarks/expected_cost_proposal_replay.py', 'benchmarks/prompteval_continuous.py',
             'benchmarks/grounded.py', 'benchmarks/grounded_fixture.py', 'benchmarks/typed_policy.py',
             'cpo/expected_cost_proposal_cycle.py', 'cpo/cycle.py', 'cpo/optimizer.py',
             'cpo/expected_qualification.py', 'cpo/paired_qualification.py')
    design = {
        'protocol': 'cpo-expected-cost-proposal-replay-v1', 'continuousReportSha256': SOURCE,
        'continuousPlanSha256': {phase: digest(item[0]) for phase, item in phases.items()},
        'caps': CAPS, 'qualificationRules': RULES, 'controlModes': continuous.GEPA,
        'bootstrap': BOOTSTRAP, 'typedFixturePlanSha256': digest(grounded.plan()),
        'scope': ('Preserve search and deployment at every proposal search cap. Reproduce the original full-cap '
                  'CPO and GEPA control totals. Compare the new proposal cycle with a deterministic typed proposer.'),
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
    }
    return design, phases


def archive_step(matrix, incumbent, layout, plan):
    train, validation, cohort = ([Row(str(case), 'task') for case in layout[key]]
                                for key in ('train', 'validation', 'qualify'))
    search_log, qualification = {}, {}
    alternatives = layout['alternatives']
    available = deque(alternatives[2:])

    def observe(prompt, row):
        passed = matrix[int(prompt)][int(row.id)] == '1'
        search_log[prompt, int(row.id)] = passed
        return Observation(passed, {'correct': passed})

    def qualify(prompt, row, repeat):
        case = int(row.id)
        if repeat != 0 or case not in layout['qualify'] or (prompt, case) in qualification:
            raise ValueError('The new cycle dispatched outside the sealed qualification panel')
        value = qualification[prompt, case] = matrix[int(prompt)][case] == '1'
        return value

    def propose(_parent, _feedback, _history, width):
        proposals = tuple(available.popleft() for _ in range(min(width, len(available))))
        return ProposalBatch(proposals, exhausted=not available)

    result = run_expected_cost_proposal_cycle(
        incumbent, train, validation, cohort, observe, propose, metric_limit=plan['evaluationLookupLimit'],
        rounds=len(alternatives) // 2, train_per_round=plan['probeSize'], qualify=qualify,
        minimum_gain=plan['minimumQualificationGain'], seed=layout['seed'], opening_pair=ProposalPair(*alternatives[:2]),
    )
    if result.search.evaluations != len(search_log) or result.qualification_evaluations != len(qualification):
        raise ValueError('The public result and paid callbacks disagree')
    return result, cohort, digest([(prompt, case, score) for (prompt, case), score in search_log.items()])


def proposal_episode(matrix, initial, layouts, plan):
    incumbent = initial
    totals = Counter()
    decisions = []
    for layout in layouts:
        full = continuous.step(continuous.CPO[0], matrix, incumbent, layout, plan)
        ordered, rows, search_hash = archive_step(matrix, incumbent, layout, plan)
        if (ordered.prompt, ordered.search.prompt, ordered.search.evaluations, search_hash) != (
                full['selected'], full['challenger'], full['searchLookups'], full['searchSha256']):
            raise ValueError('Expected-cost qualification changed the proposal search or deployment path')
        complete = {(p, case): passed for p, case, passed in full['qualification']}
        seeded = 0
        if ordered.qualification is not None:
            decision = certify_paired_qualification(
                incumbent, ordered.search.prompt, rows, lambda p, row, _: complete[p, int(row.id)],
                minimum_gain=plan['minimumQualificationGain'], seed=layout['seed'],
            )
            if decision.prompt != ordered.prompt or decision.status != ordered.qualification.status:
                raise ValueError('The seeded proof resolved a different decision')
            seeded = len(decision.observations)
        totals.update(searchLookups=full['searchLookups'], full=full['qualificationLookups'],
                      seeded=seeded, expected=ordered.qualification_evaluations,
                      promotions=int(incumbent != ordered.prompt), reflections=ordered.search.reflections)
        records = () if ordered.qualification is None else ordered.qualification.observations
        decisions.append((incumbent, ordered.search.prompt, ordered.prompt, search_hash,
                          [(reply.prompt, reply.row_id, reply.repeat, reply.passed) for reply in records]))
        incumbent = ordered.prompt
    return int(incumbent), totals, decisions


def measure_phase(plan, panels, references):
    ge = continuous.GEPA
    names = (*ge, *(f'cpo-{cap}' for cap in CAPS))
    results, totals, subjects = {}, {label: Counter() for label in names}, {}
    for panel in panels:
        subject, model, matrix = (panel[k] for k in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = plan['holdoutCaseIDs'][subject]
        finals = {label: [] for label in names}
        counters = {label: Counter() for label in names}
        traces = {label: [] for label in names}
        for seed in plan['seeds']:
            start, layouts = continuous.schedule(len(matrix[0]), len(matrix), held, seed, plan)
            for cap in CAPS:
                label = f'cpo-{cap}'
                final, used, steps = proposal_episode(matrix, start, layouts, {**plan, 'evaluationLookupLimit': cap})
                counters[label].update(used)
                finals[label].append(final)
                traces[label].append(steps)
            for label in ge:
                current = start
                steps = []
                for layout in layouts:
                    step = continuous.step(label, matrix, current, layout, plan)
                    counters[label].update({k: step[k] for k in ('searchLookups', 'qualificationLookups')})
                    counters[label]['promotions'] += current != step['selected']
                    current = step['selected']
                    steps.append(step)
                finals[label].append(int(current))
                traces[label].append(steps)
        vectors = {label: [sum(matrix[prompt][case] == '1' for prompt in choices) for case in held]
                   for label, choices in finals.items()}
        for label, scores in vectors.items():
            counters[label]['holdoutPasses'] = sum(scores)
        stored = references[name]['totals']
        for label in ge:
            if counters[label] != stored[label]:
                raise ValueError(f'GEPA control totals differ from the original report for {name}/{label}')
        original = counters[f'cpo-{CAPS[-1]}']
        if any((original['full'] if key == 'qualificationLookups' else original[key]) != value
               for key, value in stored[continuous.CPO[0]].items()):
            raise ValueError(f'Full-budget CPO totals differ from the original report for {name}')
        by_subject = subjects.setdefault(subject, {label: [0] * len(held) for label in names})
        for label in names:
            counters[label]['paidLookups'] = counters[label]['searchLookups'] + (
                counters[label]['qualificationLookups'] if label in ge else counters[label]['expected'])
            totals[label].update(counters[label])
            for index, value in enumerate(vectors[label]):
                by_subject[label][index] += value
        results[name] = {label: {**counts, 'traceSha256': digest(traces[label])} for label, counts in counters.items()}
    return {'panels': results, 'totals': totals, 'pairedComparisons': paired_ranges(totals, subjects)}


def paired_ranges(totals, subjects):
    rng = Random(BOOTSTRAP['seed'])
    labels = tuple(totals)
    choices = {f'cpo-{cap}': [] for cap in CAPS}
    for _ in range(BOOTSTRAP['draws']):
        passed = Counter()
        for subject in sorted(subjects):
            values = subjects[subject]
            count = len(values[labels[0]])
            sampled = rng.choices(range(count), k=count)
            for label in labels:
                passed[label] += sum(values[label][idx] for idx in sampled)
        for label, samples in choices.items():
            samples.append(min(passed[label] - passed[control] for control in continuous.GEPA))
    return {label: {
        'jointPairedRange95': interval(samples),
        'lookupDelta': {control: totals[label]['paidLookups'] - totals[control]['paidLookups']
                        for control in continuous.GEPA},
        'passDelta': {control: totals[label]['holdoutPasses'] - totals[control]['holdoutPasses']
                      for control in continuous.GEPA},
    } for label, samples in choices.items()}


def typed_replay():
    def exercise(operation, task, splits):
        rows = {item['id']: item for fold in ('train', 'validation', 'holdout') for item in splits[fold]}
        training = [{k: item[k] for k in ('id', 'input', 'expected')} for item in splits['train']]
        search, reflection = [], []

        def score(prompt, row):
            item = rows[row.id]
            text = grounded_fixture.respond({'task': task, 'role': 'evaluation', 'instruction': prompt,
                                            'input': item['input']})
            passed, matched = grounded.score(text, item['expected'])
            return Observation(passed, {'id': row.id, 'observed': text}, matched)

        def observe(prompt, row):
            reply = score(prompt, row)
            search.append((prompt, row.id, reply.passed, reply.matched_fields))
            return reply

        def reflect(parent, feedback, history, _width):
            opening = not reflection
            request = {'task': task, 'current': parent, 'labeledTraining': training,
                       'recentFeedback': [item.feedback for _, item in feedback], 'candidateHistory': history}
            reflected = grounded_fixture.respond({'task': task, 'role': 'reflection',
                                                  'instruction': grounded.OPENING if opening else grounded.UPDATE,
                                                  'input': request})
            reflection.append(digest(request))
            if opening:
                return ProposalPair(*grounded.proposals(reflected, parent, ('rewrite', 'repair')))
            return grounded.proposals(reflected, parent, ('instruction',))

        def panel(fold):
            return [Row(item['id'], task, item['critical'], len(item['expected'])) for item in splits[fold]]

        result = operation(grounded.BASELINE, panel('train'), panel('validation'), panel('holdout'), observe,
                           reflect, metric_limit=grounded.METRIC_LIMIT, rounds=grounded.REFLECTION_LIMIT,
                           train_per_round=grounded.MINIBATCH, qualify=lambda p, row, _: score(p, row).passed,
                           seed=grounded.SEED, field_credit=True, repeats=grounded.REPEATS)
        return result, search, reflection

    results = {}
    for task, splits in grounded.cohorts(grounded.SEED).items():
        full, search, reflection = exercise(run_cycle, task, splits)
        trial, second_search, second_reflection = exercise(run_expected_cost_proposal_cycle, task, splits)
        if (full.search, full.prompt, search, reflection) != (trial.search, trial.prompt, second_search, second_reflection):
            raise ValueError(f'Typed fixture changed proposal feedback or deployment for {task}')
        results[task] = {'searchLookups': len(search), 'reflections': len(reflection),
                         'fullQualification': full.qualification_evaluations,
                         'orderedQualification': trial.qualification_evaluations,
                         'promoted': trial.promoted, 'searchSha256': digest(search),
                         'reflectionSha256': digest(reflection)}
    return results


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, phases = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != inputs[0]['gepaVersion'] for inputs in phases.values()):
        cli.error('Use the pinned GEPA wheel')
    report = {'design': design, 'designSha256': seal, 'typedFixture': typed_replay(),
              'results': {phase: measure_phase(*inputs) for phase, inputs in phases.items()}}
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
