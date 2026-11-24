"""Compare both settled CPO runners and native GEPA on one shared draft roster."""

import argparse
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random

from benchmarks import grounded, grounded_staged as staged, grounded_staged_policy_comparison as shared
from benchmarks import grounded_witness_episode as witness
from benchmarks import typed_policy
from cpo import Observation
from cpo._contract import digest
from cpo.feedback_episode import run_feedback_episode
from cpo.paired_qualification import certify_paired_qualification
from cpo.settled_episode import EpisodeCycle, run_settled_episode


ROOT = witness.ROOT
CYCLES, TRAIN, VALIDATION, ADMISSION, DRAFTS = 3, 16, 6, 4, 4
SEED = 819407
CPO_CAP, GEPA_CAP = 19, 32
SETTLED, FEEDBACK = 'cpo-settled', 'cpo-feedback'
CPO = {SETTLED: run_settled_episode, FEEDBACK: run_feedback_episode}
ARMS = (*CPO, *witness.GEPA)
FILES = ('plan.json', 'wire.jsonl', 'result.json')


def cohorts():
    prior, staged_prior = typed_policy.cohorts(grounded.SEED), staged.cohorts()
    tasks = {}
    for task, groups in witness.cohorts().items():
        seen = {row['input'] for dataset in (groups, prior[task], staged_prior[task])
                for panel in dataset.values() for row in panel}
        validation = []
        rng = Random(f'{SEED}:{task}:validation')
        for index in range(32000, 33000):
            if task == 'ticket':
                inputs, expected, critical = typed_policy.ticket(index, rng)
            elif task == 'warehouse':
                regime = typed_policy.WAREHOUSE[index % len(typed_policy.WAREHOUSE)]
                inputs, expected, critical = typed_policy.warehouse(index, rng, regime)
            else:
                regime = typed_policy.OUTAGE[index % len(typed_policy.OUTAGE)]
                inputs, expected, critical = typed_policy.outage(index, rng, regime)
            if critical or inputs in seen:
                continue
            seen.add(inputs)
            validation.append({'id': f'settled-{task}-validation-{len(validation) + 1:02}',
                               'input': inputs, 'expected': expected, 'critical': critical})
            if len(validation) == CYCLES * VALIDATION:
                break
        if len(validation) != CYCLES * VALIDATION:
            raise ValueError('The comparison requires disjoint noncritical screening cases')
        tasks[task] = {**groups, 'train': groups['train'][:CYCLES * TRAIN], 'validation': validation,
                       'admission': groups['admission'][:CYCLES * ADMISSION]}
    return tasks


def prepare():
    tasks = cohorts()
    paths = ('benchmarks/settled_episode_prospective.py', 'benchmarks/settled_episode_prospective_fixture.py',
             'benchmarks/grounded_witness_episode.py', 'benchmarks/grounded.py', 'benchmarks/grounded_staged.py',
             'benchmarks/grounded_staged_policy_comparison.py', 'benchmarks/grounded_fixture.py',
             'benchmarks/gepa_disjoint_cases.py', 'benchmarks/prompteval_transfer.py', 'benchmarks/typed_policy.py',
             'requirements-benchmark.txt')
    paths += tuple(str(path.relative_to(ROOT)) for path in sorted((ROOT / 'cpo').glob('*.py')))
    limits = {
        'reflection': len(tasks) * CYCLES * DRAFTS,
        'evaluation': len(tasks) * (len(CPO) * (CYCLES * CPO_CAP + 2) + len(witness.GEPA) * CYCLES * GEPA_CAP),
        'admission': len(tasks) * len(ARMS) * CYCLES * 2 * ADMISSION,
        'qualification': sum(len(groups['holdout']) for groups in tasks.values()) * (len(ARMS) + 1) * grounded.REPEATS,
    }
    plan = {'protocol': 'portable-settled-episode-comparison-development-v1',
            'sourceSha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in paths},
            'datasetSha256': digest(tasks), 'seed': SEED, 'arms': ARMS, 'candidate': FEEDBACK,
            'gepaVersion': '0.1.4', 'cycles': CYCLES, 'trainingCasesPerCycle': TRAIN,
            'validationCasesPerCycle': VALIDATION, 'admissionCasesPerCycle': ADMISSION,
            'openingTrainingProbes': 2, 'repeats': grounded.REPEATS, 'admissionRepeats': 1,
            'draftsPerCycle': DRAFTS, 'maxChallengersPerCycle': 2 * DRAFTS,
            'searchCap': CYCLES * GEPA_CAP,
            'perCycleSearchCaps': {**dict.fromkeys(CPO, CPO_CAP), **dict.fromkeys(witness.GEPA, GEPA_CAP)},
            'logicalLimitsByRole': limits, 'physicalLimitsByRole': limits, 'requestCeiling': sum(limits.values()),
            'gate': witness.DEVELOPMENT_GATE,
            'caseRule': 'Both optimizers screen on the same noncritical validation cases; admission and holdout '
                        'retain the original critical labels.',
            'proposalRule': 'Draft from four nonoverlapping training blocks per cycle. All arms receive each valid '
                            'pair in order. Drop a pair if its prompts repeat the initial prompt or an earlier pair.',
            'tallyRule': 'Charge all shared drafting to every arm. Evaluation and admission replies share by exact '
                         'request while each arm records its logical and distinct attributed search uses.'}
    return tasks, plan


def draft_cycles(task, groups, dispatch, journal):
    initial = grounded.BASELINE
    seen, cycles, blocks, drafts = {initial}, [], [], []
    training_width = TRAIN // DRAFTS
    for index in range(CYCLES):
        training = groups['train'][index * TRAIN:(index + 1) * TRAIN]
        roster = []
        for slot in range(DRAFTS):
            block = training[slot * training_width:(slot + 1) * training_width]
            examples = {'task': task, 'current': initial, 'labeledTraining': block, 'recentFeedback': []}
            reply = dispatch(f'roster-{slot + 1}', 'reflection', grounded.OPENING, examples)
            drafts.append(journal.sequence)
            proposals = grounded.proposals(reply, initial, ('rewrite', 'repair'))
            if proposals and seen.isdisjoint(proposals):
                roster.extend(proposals)
                seen.update(proposals)
        validation = groups['validation'][index * VALIDATION:(index + 1) * VALIDATION]
        admission = groups['admission'][index * ADMISSION:(index + 1) * ADMISSION]
        cycles.append(EpisodeCycle(tuple(roster), tuple(staged.cases(task, validation)),
                                   tuple(staged.cases(task, admission)), SEED + index))
        blocks.append(training)
    return cycles, blocks, drafts


def choose(task, groups, dispatch, journal):
    initial = grounded.BASELINE
    cases = {row['id']: row for panel in groups.values() for row in panel}
    cycles, blocks, drafts = draft_cycles(task, groups, dispatch, journal)
    training = staged.cases(task, blocks[0][:2])
    selected, decisions = {'initial': initial}, {}
    order = list(ARMS)
    Random(f'{SEED}:{task}').shuffle(order)
    for arm in order:
        def grade(prompt, case, role, repeat=None):
            spec = cases[case]
            return grounded.score(dispatch(arm, role, prompt, spec['input'], repeat=repeat), spec['expected'])[0]

        def evaluate(prompt, row):
            return Observation(grade(prompt, row.id, 'evaluation'), {})

        def probe(prompt, row):
            return grade(prompt, row.id, 'evaluation')

        def qualify(prompt, row, repeat):
            return grade(prompt, row.id, 'admission', repeat)

        before = len(journal.search_uses[arm])
        journal.search_uses[arm].extend(drafts)
        if arm in CPO:
            result = CPO[arm](initial, training, cycles, evaluate, probe=probe, qualify=qualify)
            selected[arm] = result.prompt
            schedules = getattr(result, 'cycle_schedules', (result.schedule,) * CYCLES)
            decisions[arm] = [{'schedule': schedule, 'nominee': step.search.finalist, 'prompt': step.prompt,
                               'admission': step.qualification.status if step.qualification else 'skipped',
                               'validationLookups': step.search.evaluations,
                               'admissionLookups': step.qualification_evaluations}
                              for schedule, step in zip(schedules, result.cycles, strict=True)]
            if result.training_evaluations != 2 or any(step.search.evaluations > CPO_CAP for step in result.cycles):
                raise ValueError('CPO exceeded its sealed training or validation shape')
            if result.evaluations + len(drafts) != len(journal.search_uses[arm]) - before:
                raise ValueError('CPO callback counts must reconcile with the paired journal')
        else:
            incumbent, log = initial, []
            for cycle, block in zip(cycles, blocks, strict=True):
                known = {}
                train = tuple(row['id'] for row in block)
                anchors = tuple(row.id for row in cycle.validation)
                allowed = set(train).union(anchors)

                def observe(prompt, case):
                    key = prompt, case
                    if prompt not in (incumbent, *cycle.candidates) or case not in allowed:
                        raise ValueError('Native search left the sealed roster or case split')
                    if key not in known:
                        if len(known) == GEPA_CAP:
                            raise ValueError('Native search exceeded its per-cycle cap')
                        known[key] = grade(prompt, case, 'evaluation')
                    return known[key]

                winner = witness.native(incumbent, cycle.candidates, train, anchors, observe, cap=GEPA_CAP,
                                        batched=arm == witness.GEPA[-1], seed=cycle.seed) if cycle.candidates else incumbent
                if winner not in (incumbent, *cycle.candidates):
                    raise ValueError('The native nominee must come from the shared roster')
                proof = certify_paired_qualification(incumbent, winner, cycle.qualification, qualify, seed=cycle.seed)
                log.append({'nominee': winner if winner != incumbent else None, 'prompt': proof.prompt,
                            'admission': proof.status, 'validationAndTrainingLookups': len(known),
                            'challengerLookups': sum(prompt != incumbent for prompt, _ in known),
                            'admissionLookups': len(proof.observations)})
                incumbent = proof.prompt
            selected[arm], decisions[arm] = incumbent, log
            count = sum(step['validationAndTrainingLookups'] + step['admissionLookups'] for step in log)
            if count + len(drafts) != len(journal.search_uses[arm]) - before:
                raise ValueError('GEPA callback counts must reconcile with the paired journal')
    return selected, decisions, [len(cycle.candidates) for cycle in cycles]


def run(seal, directory, respond, *, delivery):
    tasks, plan = prepare()
    if seal != digest(plan) or version('gepa') != plan['gepaVersion'] or delivery not in ('fixture', 'model'):
        raise ValueError('Use the sealed plan, pinned GEPA, and declared delivery')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**plan, 'planSha256': seal, 'delivery': delivery})
    selected, decisions, rosters, outcomes = {}, {}, {}, {}
    with (directory / 'wire.jsonl').open('x') as wire:
        journal = shared.Journal(wire, plan, respond)
        journal.request_limits['admission'] = CYCLES * ADMISSION * 2
        allowed = {task: {split: {row['input'] for row in rows} for split, rows in groups.items()}
                   for task, groups in tasks.items()}
        schemas = {task: staged.schema(groups) for task, groups in tasks.items()}

        def dispatch(task, arm, role, prompt, inputs, *, repeat=None):
            request = {'task': task, 'role': role, 'instruction': prompt, 'input': inputs}
            if role != 'reflection':
                splits = {'evaluation': ('train', 'validation'), 'admission': ('admission',),
                          'qualification': ('holdout',)}[role]
                if not any(inputs in allowed[task][split] for split in splits):
                    raise ValueError('The request left its sealed case split')
                request['jsonSchema'] = schemas[task]
            if repeat is not None:
                request['repeat'] = repeat
            return journal.send(arm, request)

        try:
            for task, groups in tasks.items():
                selected[task], decisions[task], rosters[task] = choose(
                    task, groups, lambda *args, **kwargs: dispatch(task, *args, **kwargs), journal,
                )
            for task, groups in tasks.items():
                paired = grounded.qualify_task(task, groups['holdout'], selected[task],
                                               lambda *args, **kwargs: dispatch(task, *args, **kwargs))
                outcomes[task] = [{'id': row, 'repeat': repeat, 'critical': critical, 'passes': passes}
                                  for (row, repeat), (critical, passes) in paired.items()]
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None
    costs = {'logicalSearchUses': {arm: len(journal.search_uses[arm]) for arm in ARMS},
             'attributedSearchRequests': {arm: len(set(journal.search_uses[arm])) for arm in ARMS}}
    projected = {task: [{**row, 'passes': {**row['passes'], 'cpo': row['passes'][FEEDBACK]}} for row in panel]
                 for task, panel in outcomes.items()}
    verdicts = {name: staged.grade(projected, {**spent, 'cpo': spent[FEEDBACK]}, plan['gate'],
                                   controls=(SETTLED, *witness.GEPA)) for name, spent in costs.items()}
    result = {'planSha256': seal, 'delivery': delivery, 'selected': selected, 'decisions': decisions,
              'rosterSizes': rosters, 'holdout': outcomes, 'searchCosts': costs,
              'logicalCallsByRole': dict(journal.logical), 'physicalCallsByRole': dict(journal.physical),
              'verdicts': verdicts, 'qualifiedOnBothMeasures': all(row['qualified'] for row in verdicts.values())}
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate output directory')
    raw = {name: (directory / name).read_bytes() for name in FILES}
    manifest = grounded.load_json(raw['plan.json'])
    pending = iter(raw['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        start, end = next(pending, None), next(pending, None)
        if start is None or end is None:
            raise ValueError('The journal contains an incomplete reply')
        sent, reply = grounded.load_json(start), grounded.load_json(end)
        if sent['sequence'] != sequence or reply['sequence'] != sequence or sent['request'] != request:
            raise ValueError('The replay request differs from the sealed journal')
        return reply['response']

    result = run(manifest['planSha256'], fresh, respond, delivery=manifest['delivery'])
    if next(pending, None) is not None or any((fresh / name).read_bytes() != data for name, data in raw.items()):
        raise ValueError('The comparison archive differs from its exact replay')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fixture', metavar='PLAN_SHA256')
    mode.add_argument('--replay', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    tasks, plan = prepare()
    seal = digest(plan)
    if not args.fixture and not args.replay and not args.out:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.out is None or args.out.exists() or not (args.fixture or args.replay):
        parser.error('Rehearsal requires a seal or archive and a fresh output path')
    if args.replay:
        replay(args.replay, args.out)
    else:
        from benchmarks.settled_episode_prospective_fixture import responder

        run(args.fixture, args.out, responder(tasks), delivery='fixture')


if __name__ == '__main__':
    main()
