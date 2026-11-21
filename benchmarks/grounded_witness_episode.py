"""Run a prospective paired comparison of the one-admission witness episode."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from unittest.mock import patch

from benchmarks import grounded, grounded_staged as staged, grounded_staged_policy_comparison as shared
from benchmarks import prompteval_transfer, typed_policy
from benchmarks.gepa_disjoint_cases import CaseRows
from cpo import Observation
from cpo._contract import digest
from cpo.paired_qualification import certify_paired_qualification
from cpo.rotating_witness.episode import WitnessCycle, run_rotating_witness_episode


ROOT = staged.ROOT
SEED, CYCLES, TRAIN_ROWS = 198307, 4, 16
SPLITS = {'train': CYCLES * TRAIN_ROWS, 'validation': 24, 'admission': CYCLES * 8, 'holdout': 18, 'confirmation': 8}
GEPA = ('gepa-sequential', 'gepa-batched')
CPO = {'cpo-one-admission': 1, 'cpo-four-admissions': CYCLES}
ARMS = (*CPO, *GEPA)
CANDIDATE = next(iter(CPO))
CAPS = {**dict.fromkeys(CPO, 30), **dict.fromkeys(GEPA, 32)}
GEPA_ANCHORS = 8
DEVELOPMENT_GATE = {'minimumTaskPasses': 27, 'minimumAddedPasses': 8, 'efficiencyPercent': 90}
CONFIRMATION_GATE = {'minimumTaskPasses': 12, 'minimumAddedPasses': 4, 'efficiencyPercent': 90}
FILES = ('plan.json', 'wire.jsonl', 'result.json')


def cohorts():
    prior, staged_prior = typed_policy.cohorts(grounded.SEED), staged.cohorts()
    tasks = {}
    for task in typed_policy.TASKS:
        seen = {row['input'] for archived in (prior, staged_prior) for panel in archived[task].values() for row in panel}
        rng = Random(f'{SEED}:{task}')
        index, groups = 1024, {}
        for split, count in SPLITS.items():
            rows = []
            for offset in range(count):
                for _ in range(100):
                    if task == 'ticket':
                        facts, expected, critical = typed_policy.ticket(index, rng)
                    elif task == 'warehouse':
                        facts, expected, critical = typed_policy.warehouse(
                            index, rng, typed_policy.WAREHOUSE[offset % len(typed_policy.WAREHOUSE)])
                    else:
                        regime = typed_policy.OUTAGE[(offset * 5) % len(typed_policy.OUTAGE)]
                        facts, expected, critical = typed_policy.outage(index, rng, regime)
                    index += 1
                    if facts not in seen:
                        break
                else:
                    raise ValueError('The episode cohort could not produce unique case facts')
                seen.add(facts)
                rows.append({'id': f'witness-{task}-{split}-{offset + 1:02}', 'input': facts,
                             'expected': expected, 'critical': critical})
            groups[split] = rows
        tasks[task] = groups
    return tasks


def archive_bytes(directory):
    return {name: (directory / name).read_bytes() for name in FILES}


def prepare(development=None):
    tasks = cohorts()
    paths = ('benchmarks/grounded_witness_episode.py', 'benchmarks/grounded_witness_episode_fixture.py',
             'benchmarks/grounded.py', 'benchmarks/grounded_fixture.py', 'benchmarks/grounded_staged.py',
             'benchmarks/grounded_staged_policy_comparison.py', 'benchmarks/prompteval_transfer.py',
             'benchmarks/gepa_disjoint_cases.py', 'benchmarks/typed_policy.py', 'requirements-benchmark.txt')
    paths += tuple(str(path.relative_to(ROOT)) for pattern in ('*.py', 'rotating_witness/*.py')
                   for path in sorted((ROOT / 'cpo').glob(pattern)))
    repeats, task_count = grounded.REPEATS, len(tasks)
    limits = {'reflection': task_count * CYCLES,
              'evaluation': task_count * CYCLES * sum(CAPS.values()),
              'admission': task_count * (sum(CPO.values()) + len(GEPA)) * 2 * (SPLITS['admission'] // CYCLES) * repeats,
              'qualification': task_count * (1 + len(ARMS)) * SPLITS['holdout'] * repeats}
    plan = {'protocol': 'portable-grounded-witness-episode-development-v1', 'sourceSha256': {
                name: sha256((ROOT / name).read_bytes()).hexdigest() for name in paths},
            'datasetSha256': digest(tasks), 'seed': SEED, 'splitSizes': SPLITS, 'repeats': repeats,
            'gepaVersion': '0.1.4', 'arms': list(ARMS), 'candidate': CANDIDATE, 'cycles': CYCLES,
            'perCycleSearchCaps': CAPS, 'maxAdmissionAttempts': {**CPO, **dict.fromkeys(GEPA, 1)},
            'gepaValidationAnchors': GEPA_ANCHORS, 'gate': DEVELOPMENT_GATE,
            'proposalRule': 'Generate a shared rewrite and repair from each cycle training panel and the initial prompt.',
            'emptySlotRule': 'An invalid pair yields an empty roster. A proposal equal to the current incumbent cannot nominate it.',
            'logicalLimitsByRole': limits, 'physicalLimitsByRole': limits, 'requestCeiling': sum(limits.values())}
    if development is None:
        return tasks, plan, None

    original = archive_bytes(development)
    with TemporaryDirectory(prefix='cpo-witness-bind-') as scratch:
        prior = replay(development, Path(scratch) / 'verified')
    if archive_bytes(development) != original or not prior['qualifiedOnBothMeasures']:
        raise ValueError('Independent confirmation requires an exact, qualifying development archive')
    cap = sum(len(set(prior['selected'][task].values())) * len(groups['confirmation']) * repeats
              for task, groups in tasks.items())
    plan.update(protocol='portable-grounded-witness-episode-confirmation-v1',
                gate=CONFIRMATION_GATE, logicalLimitsByRole={'qualification': cap},
                physicalLimitsByRole={'qualification': cap}, requestCeiling=cap,
                developmentPlanSha256=prior['planSha256'], developmentDelivery=prior['delivery'],
                developmentArchiveSha256={name: sha256(raw).hexdigest() for name, raw in original.items()},
                selectedSha256=digest(prior['selected']))
    return tasks, plan, prior


class Journal(shared.Journal):
    def __init__(self, wire, plan, respond):
        super().__init__(wire, {**plan, 'searchCap': CYCLES * max(CAPS.values())}, respond)
        self.request_limits['admission'] = 2 * SPLITS['admission'] * grounded.REPEATS


def native(incumbent, proposals, train, validation, evaluate, *, batched, cap, seed):
    """Keep GEPA's full-round reserve and disjoint training and validation identities."""
    module = import_module('gepa.optimize_anything')
    original = module.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        first, second = [CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if first.by_id.keys() & second.by_id.keys():
            raise ValueError('Native train and validation IDs overlap')
        return original(*args, dataset=first, valset=second, **settings)

    with patch.object(module, 'optimize_anything', disjoint), patch.object(prompteval_transfer, 'LOOKUP_LIMIT', cap):
        return prompteval_transfer.optimize_gepa(incumbent, proposals, train, validation, evaluate,
                                                batched=batched, seed=seed)


def choose(task, groups, dispatch, journal):
    initial = grounded.BASELINE
    references = {row['id']: row for panel in groups.values() for row in panel}
    blocks = [groups['train'][i * TRAIN_ROWS:(i + 1) * TRAIN_ROWS] for i in range(CYCLES)]
    validation = tuple(staged.cases(task, groups['validation']))
    admission_rows = SPLITS['admission'] // CYCLES
    cycles, shared_sequences = [], []
    for cycle, block in enumerate(blocks):
        examples = {'task': task, 'current': initial, 'labeledTraining': block, 'recentFeedback': []}
        text = dispatch('roster', 'reflection', grounded.OPENING, examples)
        shared_sequences.append(journal.sequence)
        proposals = grounded.proposals(text, initial, ('rewrite', 'repair'))
        admission = groups['admission'][cycle * admission_rows:(cycle + 1) * admission_rows]
        cycles.append(WitnessCycle(proposals, validation, tuple(staged.cases(task, admission)), SEED + cycle))

    selected, decisions = {'initial': initial}, {}
    order = list(ARMS)
    Random(f'{SEED}:{task}').shuffle(order)
    for arm in order:
        def evaluate(prompt, row):
            spec = references[row.id]
            text = dispatch(arm, 'evaluation', prompt, spec['input'])
            return Observation(grounded.score(text, spec['expected'])[0], {})

        def qualify(prompt, row, repeat):
            spec = references[row.id]
            text = dispatch(arm, 'admission', prompt, spec['input'], repeat=repeat)
            return grounded.score(text, spec['expected'])[0]

        if arm in CPO:
            result = run_rotating_witness_episode(initial, cycles, evaluate, qualify=qualify, metric_limit=CAPS[arm],
                                                  repeats=grounded.REPEATS, max_admissions=CPO[arm])
            selected[arm] = result.prompt
            decisions[arm] = [{'nominee': entry.search.finalist, 'prompt': entry.prompt,
                               'admission': entry.qualification.status if entry.qualification else 'no-nominee'}
                              for entry in result.cycles]
        else:
            incumbent, log = initial, []
            for cycle, block in zip(cycles, blocks, strict=True):
                known = {}
                train = tuple(row['id'] for row in block)
                anchors = tuple(row.id for row in cycle.validation[:GEPA_ANCHORS])
                allowed = set(train).union(anchors)

                def score(prompt, case):
                    key = prompt, case
                    if prompt not in (incumbent, *cycle.candidates) or case not in allowed:
                        raise ValueError('Native search left its candidate or case scope')
                    if key not in known:
                        if len(known) >= CAPS[arm]:
                            raise ValueError('Native search exceeded the per-cycle cap')
                        row = references[case]
                        reply = dispatch(arm, 'evaluation', prompt, row['input'])
                        known[key] = grounded.score(reply, row['expected'])[0]
                    return known[key]

                nominee = native(incumbent, cycle.candidates, train, anchors, score, batched=arm == GEPA[-1],
                                 cap=CAPS[arm], seed=cycle.seed) if cycle.candidates else incumbent
                if nominee not in (incumbent, *cycle.candidates):
                    raise ValueError('The native selector nominated an out-of-scope prompt')
                proof = certify_paired_qualification(incumbent, nominee, cycle.qualification, qualify,
                                                     seed=cycle.seed, repeats=grounded.REPEATS)
                log.append({'nominee': nominee, 'prompt': proof.prompt,
                            'admission': proof.status if nominee != incumbent else 'no-nominee'})
                if nominee != incumbent:
                    incumbent = proof.prompt
                    break
            selected[arm], decisions[arm] = incumbent, log
        journal.search_uses[arm].extend(shared_sequences[:len(decisions[arm])])
    return selected, decisions


def finish(plan, outcomes, costs):
    projected = {task: [{**row, 'passes': {**row['passes'], 'cpo': row['passes'][CANDIDATE]}} for row in panel]
                 for task, panel in outcomes.items()}
    return {name: staged.grade(projected, {**amounts, 'cpo': amounts[CANDIDATE]}, plan['gate'], controls=GEPA)
            for name, amounts in costs.items()}


def run(seal, directory, respond, *, delivery, development=None):
    tasks, plan, prior = prepare(development)
    if seal != digest(plan) or version('gepa') != plan['gepaVersion'] or delivery not in ('fixture', 'model'):
        raise ValueError('Use the sealed plan, pinned GEPA, and declared delivery')
    if prior is not None and (prior['delivery'] != delivery or directory.resolve().is_relative_to(development.resolve())):
        raise ValueError('Confirmation needs matching delivery and its own fresh archive')
    directory.mkdir(mode=0o700)
    staged.save(directory / 'plan.json', {**plan, 'planSha256': seal, 'delivery': delivery})
    selected, decisions = ({}, {}) if prior is None else (prior['selected'], prior['admissions'])
    outcomes = {}
    scoring = 'holdout' if prior is None else 'confirmation'
    allowed = {task: {split: {row['input'] for row in rows} for split, rows in groups.items()}
               for task, groups in tasks.items()}
    schemas = {task: staged.schema(groups) for task, groups in tasks.items()}
    with (directory / 'wire.jsonl').open('x') as wire:
        journal = Journal(wire, plan, respond)

        def dispatch(task, arm, role, prompt, inputs, *, repeat=None):
            request = {'task': task, 'role': role, 'instruction': prompt, 'input': inputs}
            if role != 'reflection':
                splits = ('validation', 'train') if arm in GEPA else ('validation',)
                if role != 'evaluation':
                    splits = ('admission',) if role == 'admission' else (scoring,)
                if not any(inputs in allowed[task][split] for split in splits):
                    raise ValueError('The request left its sealed case split')
                request['jsonSchema'] = schemas[task]
            if repeat is not None:
                request['repeat'] = repeat
            return journal.send(arm, request)

        try:
            if prior is None:
                for name, groups in tasks.items():
                    search = {part: groups[part] for part in ('train', 'validation', 'admission')}
                    selected[name], decisions[name] = choose(name, search, lambda *a, **k: dispatch(name, *a, **k), journal)
            for name, groups in tasks.items():
                paired = grounded.qualify_task(name, groups[scoring], selected[name], lambda *a, **k: dispatch(name, *a, **k))
                outcomes[name] = [{'id': row, 'repeat': repeat, 'critical': critical, 'passes': passes}
                                  for (row, repeat), (critical, passes) in paired.items()]
        except grounded.ResponderFailed as failure:
            raise failure.__cause__ from None

    uses = {arm: journal.search_uses[arm] for arm in ARMS}
    if prior is not None and dict(journal.physical) != plan['physicalLimitsByRole']:
        raise ValueError('Confirmation must complete the exact bound scoring schedule')
    costs = ({'logicalSearchUses': {arm: len(samples) for arm, samples in uses.items()},
              'attributedSearchRequests': {arm: len(set(samples)) for arm, samples in uses.items()}}
             if prior is None else prior['searchCosts'])
    verdicts = finish(plan, outcomes, costs)
    result = {'planSha256': seal, 'delivery': delivery, 'selected': selected, 'admissions': decisions,
              'holdout': outcomes, 'searchCosts': costs, 'logicalCallsByRole': dict(journal.logical),
              'physicalCallsByRole': dict(journal.physical),
              'verdicts': verdicts, 'qualifiedOnBothMeasures': all(row['qualified'] for row in verdicts.values())}
    staged.save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development=None):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate output directory')
    raw = archive_bytes(directory)
    manifest = grounded.load_json(raw['plan.json'])
    pending = iter(raw['wire.jsonl'].splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        start, end = next(pending, None), next(pending, None)
        if start is None or end is None:
            raise ValueError('The fixture or provider journal contains an incomplete reply')
        sent, reply = grounded.load_json(start), grounded.load_json(end)
        if sent['sequence'] != sequence or reply['sequence'] != sequence or sent['request'] != request:
            raise ValueError('The replay request differs from the sealed journal')
        return reply['response']

    result = run(manifest['planSha256'], fresh, respond, delivery=manifest['delivery'], development=development)
    if next(pending, None) is not None or archive_bytes(fresh) != raw:
        raise ValueError('The comparison archive differs from its exact replay')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fixture')
    mode.add_argument('--replay', type=Path)
    parser.add_argument('--development', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--profile', choices=('qualifying', 'rejected'), default='qualifying')
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out):
        parser.error('Fixture and replay require a fresh output directory')
    if args.fixture:
        from benchmarks.grounded_witness_episode_fixture import responder

        result = run(args.fixture, args.out, responder(cohorts(), args.profile), delivery='fixture',
                     development=args.development)
    elif args.replay:
        result = replay(args.replay, args.out, development=args.development)
    else:
        _, plan, _ = prepare(args.development)
        result = {**plan, 'planSha256': digest(plan)}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
