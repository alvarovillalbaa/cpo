"""Run or replay a sealed, provider-neutral comparison of the published repair cycle."""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from importlib.metadata import version
from importlib.util import find_spec
import json
from os import fsync
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory

from benchmarks import feedback_budget, grounded, grounded_fixture, opening_screen_typed, typed_policy
from cpo import Observation, ProposalPair, Row
from cpo._contract import digest
from cpo.family_qualification import certify_family_qualification
from cpo.validation_guided_repair import run_validation_guided_repair_cycle


ROOT = Path(__file__).resolve().parents[1]
SEED = 66029
SPLITS = {'train': 16, 'validation': 12, 'admission': 8, 'holdout': 18, 'confirmation': 8}
ARMS = ('cpo', 'gepa-sequential', 'gepa-batched')
RETRY_LIMIT = 8
FAMILY = {'ticket': 'Channel', 'warehouse': 'Tier', 'outage': 'Plan'}
BOUNDARIES = (0, 1, 4, 5, 8, 9, 12, 14)
ROLE_LIMITS = {
    'reflection': len(typed_policy.TASKS) * (1 + 3 + 2 * grounded.REFLECTION_LIMIT),
    'evaluation': len(typed_policy.TASKS) * len(ARMS) * grounded.METRIC_LIMIT,
    'admission': len(typed_policy.TASKS) * len(ARMS) * 2 * SPLITS['admission'] * grounded.REPEATS,
    'qualification': len(typed_policy.TASKS) * (1 + len(ARMS)) * SPLITS['holdout'] * grounded.REPEATS,
}
ARCHIVE_FILES = ('plan.json', 'wire.jsonl', 'result.json')


def cohorts():
    previous = typed_policy.cohorts(grounded.SEED)
    result = {}
    for task in typed_policy.TASKS:
        seen = {row['input'] for rows in previous[task].values() for row in rows}
        rng = Random(f'{SEED}:{task}')
        index = 128
        groups = {}
        for split, size in SPLITS.items():
            rows = []
            for offset in range(size):
                if task == 'ticket':
                    facts, expected, critical = typed_policy.ticket(index, rng)
                elif task == 'warehouse':
                    regime = typed_policy.WAREHOUSE[offset % len(typed_policy.WAREHOUSE)]
                    facts, expected, critical = typed_policy.warehouse(index, rng, regime)
                else:
                    key = BOUNDARIES[offset] if split in ('admission', 'confirmation') else (5 * offset) % 16
                    for _ in range(100):
                        facts, expected, critical = typed_policy.outage(index, rng, typed_policy.OUTAGE[key])
                        if facts not in seen:
                            break
                        index += 1
                if facts in seen:
                    raise ValueError('Prospective qualification needs disjoint case inputs')
                seen.add(facts)
                rows.append({'id': f'staged-{task}-{split}-{offset + 1:02}', 'input': facts,
                             'expected': expected, 'critical': critical})
                index += 1
            groups[split] = rows
        result[task] = groups
    return result


def plan(groups, *, certify_final_draft=False, certify_opening=False):
    if any(type(flag) is not bool for flag in (certify_final_draft, certify_opening)):
        raise ValueError('Staged certificate settings must be boolean')
    names = ('benchmarks/grounded_staged.py', 'benchmarks/grounded_staged_fixture.py',
             'benchmarks/grounded.py', 'benchmarks/grounded_fixture.py', 'benchmarks/feedback_budget.py',
             'benchmarks/typed_policy.py', 'benchmarks/opening_screen_typed.py', 'cpo/_contract.py',
             'cpo/optimizer.py', 'cpo/validation_guided_repair.py', 'cpo/routed_repair_cycle.py',
             'cpo/family_qualification.py', 'cpo/paired_qualification.py', 'cpo/expected_qualification.py',
             'cpo/opening_screen_cycle.py', 'cpo/opening_repair_cycle.py', 'cpo/expected_cost_proposal_cycle.py',
             'requirements-benchmark.txt')
    if certify_final_draft:
        names += ('cpo/anchored_validation.py',)
    if certify_opening:
        names += ('cpo/opening_certificate.py',)
    sources = {}
    for name in names:
        path = Path(find_spec(f'cpo.{Path(name).stem}').origin) if name.startswith('cpo/') else ROOT / name
        sources[name] = sha256(path.read_bytes()).hexdigest()
    frozen = {'protocol': 'portable-grounded-staged-v1', 'seed': SEED, 'gepaVersion': '0.1.4', 'arms': list(ARMS),
              'sourceSha256': sources, 'corpusSha256': digest(groups), 'splitSizes': SPLITS, 'familyFields': FAMILY,
              'searchCap': grounded.METRIC_LIMIT, 'laterRetryCap': RETRY_LIMIT, 'repeats': grounded.REPEATS,
              'logicalLimitsByRole': ROLE_LIMITS, 'developmentRequestCeiling': sum(ROLE_LIMITS.values()),
              'gate': {'minimumTaskPasses': 27, 'minimumAddedPasses': 8, 'efficiencyPercent': 90},
              'scope': 'Staged CPO and two native field-scored GEPA controls with shared independent admission.'}
    if certify_final_draft:
        frozen.update(protocol='portable-grounded-staged-certified-v1', certifyFinalDraft=True)
    if certify_opening:
        protocol = 'portable-grounded-staged-combined-v1' if certify_final_draft else 'portable-grounded-staged-opening-v1'
        frozen.update(protocol=protocol, certifyOpening=True)
    return frozen


def schema(groups):
    types = {str: 'string', int: 'integer', bool: 'boolean'}
    answer = groups['train'][0]['expected']
    return {'type': 'object', 'properties': {key: {'type': types[type(value)]} for key, value in answer.items()},
            'required': list(answer), 'additionalProperties': False}


def cases(task, rows):
    return [Row(row['id'], grounded_fixture.facts(row['input'])[FAMILY[task]],
                row['critical'], len(row['expected'])) for row in rows]


def choose(task, groups, dispatch, *, certify_final_draft=False, certify_opening=False):
    train, validation, admission = (groups[name] for name in ('train', 'validation', 'admission'))
    training = [{key: row[key] for key in ('id', 'input', 'expected')} for row in train]
    train_ids = {row['id'] for row in train}
    search_rows = {row['id']: row for row in (*train, *validation)}
    admission_rows = {row['id']: row for row in admission}

    def reflection(arm, parent, feedback, *, opening=False):
        if any(item['id'] not in train_ids for item in feedback):
            raise grounded.ResponderFailed from ValueError('Only training observations may reach the proposer')
        payload = {'task': task, 'current': parent, 'labeledTraining': training, 'recentFeedback': feedback}
        text = dispatch(arm, 'reflection', grounded.OPENING if opening else grounded.UPDATE, payload)
        return grounded.proposals(text, parent, ('rewrite', 'repair') if opening else ('instruction',))

    bank = reflection('shared', grounded.BASELINE, [], opening=True)
    if not bank:
        raise ValueError('The common opening must contain two valid distinct instructions')
    selected = {'initial': grounded.BASELINE}
    decision_log = {}
    order = list(ARMS)
    Random(f'{SEED}:{task}').shuffle(order)
    for arm in order:
        def evaluate(prompt, row_id):
            row = search_rows[row_id]
            text = dispatch(arm, 'evaluation', prompt, row['input'])
            passed, fields = grounded.score(text, row['expected'])
            return Observation(passed, {'id': row_id, 'observed': text}, fields)

        def qualify(prompt, row, repeat):
            record = admission_rows[row.id]
            return grounded.score(dispatch(arm, 'admission', prompt, record['input'], repeat=repeat),
                                  record['expected'])[0]

        def reflect(parent, feedback):
            observations = list(feedback_budget.observation_records(feedback))
            return next(iter(reflection(arm, parent, observations)), parent)

        if arm == 'cpo':
            def input_features(row):
                facts = grounded_fixture.facts(search_rows[row.id]['input'])
                return {key: value for key, value in facts.items() if key != 'Reference'}

            result = run_validation_guided_repair_cycle(
                grounded.BASELINE, cases(task, train), cases(task, validation), cases(task, admission),
                lambda prompt, row: evaluate(prompt, row.id),
                lambda parent, feedback, *_: reflect(parent, [reply.feedback for _, reply in feedback]),
                input_features=input_features, opening_pair=ProposalPair(*bank), metric_limit=grounded.METRIC_LIMIT,
                qualify=qualify, repeats=grounded.REPEATS, seed=SEED, field_credit=True, retry_probe_limit=RETRY_LIMIT,
                certify_final_draft=certify_final_draft, certify_opening=certify_opening,
            )
            nominee, selected[arm] = result.search.prompt, result.prompt
            proof = result.qualification
        else:
            nominee = opening_screen_typed.gepa_select(grounded.BASELINE, bank, groups, evaluate, reflect,
                                                        cap=grounded.METRIC_LIMIT, seed=SEED,
                                                        width=2 if arm == 'gepa-batched' else 1)
            proof = certify_family_qualification(grounded.BASELINE, nominee, cases(task, admission), qualify,
                                                 repeats=grounded.REPEATS, seed=SEED)
            selected[arm] = proof.prompt
        decision_log[arm] = {'nominee': nominee, 'admission': proof.status if proof else 'no-nominee',
                             'admissionLookups': len(proof.observations) if proof else 0}
    return selected, decision_log


def grade(outcomes, costs, gate):
    totals = {arm: {task: sum(row['passes'][arm] for row in rows) for task, rows in outcomes.items()}
              for arm in ('initial', *ARMS)}
    comparisons = {}
    for arm in ('initial', *ARMS[1:]):
        deltas, critical_losses = Counter(), 0
        for rows in outcomes.values():
            for row in rows:
                delta = row['passes']['cpo'] - row['passes'][arm]
                deltas[row['id']] += delta
                critical_losses += row['critical'] and delta < 0
        gain = sum(deltas.values())
        preserves = not critical_losses and all(totals['cpo'][task] >= score for task, score in totals[arm].items())
        efficient = (arm != 'initial' and min(deltas.values()) >= 0
                     and costs['cpo'] * 100 <= costs[arm] * gate['efficiencyPercent'])
        comparisons[arm] = {'addedPasses': gain, 'criticalLosses': critical_losses,
                            'qualified': preserves and (arm == 'initial' or gain >= gate['minimumAddedPasses'] or efficient)}
    return {'passesByTask': totals, 'comparisons': comparisons,
            'qualified': (min(totals['cpo'].values()) >= gate['minimumTaskPasses']
                          and all(row['qualified'] for row in comparisons.values()))}


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write('\n')


def record(handle, value):
    handle.write(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')
    handle.flush()
    fsync(handle.fileno())


def prepare(development=None, *, certify_final_draft=False, certify_opening=False):
    groups = cohorts()
    frozen = plan(groups, certify_final_draft=certify_final_draft, certify_opening=certify_opening)
    if development is None:
        return groups, frozen, None
    snapshots = {name: (development / name).read_bytes() for name in ARCHIVE_FILES}
    with TemporaryDirectory(prefix='cpo-confirmation-bind-') as scratch:
        result = replay(development, Path(scratch) / 'verified', certify_final_draft=certify_final_draft,
                        certify_opening=certify_opening)
    if not result['outcome']['qualified']:
        raise ValueError('Independent confirmation requires a qualifying development archive')
    if any((development / name).read_bytes() != raw for name, raw in snapshots.items()):
        raise ValueError('The development archive changed during confirmation binding')
    count = len(groups) * (1 + len(ARMS)) * SPLITS['confirmation'] * grounded.REPEATS
    bound = {**frozen, 'protocol': frozen['protocol'] + '-confirmation',
             'developmentPlanSha256': result['planSha256'], 'developmentDelivery': result['delivery'],
             'developmentArchiveSha256': {key: sha256(raw).hexdigest() for key, raw in snapshots.items()},
             'promptsSha256': digest(result['selected']), 'logicalLimitsByRole': {'qualification': count},
             'confirmationRequestCeiling': count,
             'gate': {'minimumTaskPasses': 12, 'minimumAddedPasses': 4, 'efficiencyPercent': 90}}
    del bound['developmentRequestCeiling']
    return groups, bound, result


def run(seal, directory, respond, *, delivery, development=None, certify_final_draft=False, certify_opening=False):
    """Run with an explicitly supplied text responder and preserve an exact journal."""
    if development is not None and directory.resolve().is_relative_to(development.resolve()):
        raise ValueError('Confirmation requires an archive outside the development directory')
    groups, frozen, prior = prepare(development, certify_final_draft=certify_final_draft, certify_opening=certify_opening)
    if seal != digest(frozen) or version('gepa') != frozen['gepaVersion'] or delivery not in ('fixture', 'model'):
        raise ValueError('Use the current seal, pinned GEPA, and declared delivery')
    if prior is not None and prior['delivery'] != delivery:
        raise ValueError('Confirmation delivery must match the verified development archive')
    directory.mkdir(mode=0o700)
    save(directory / 'plan.json', {**frozen, 'planSha256': seal, 'delivery': delivery})
    counts, physical, costs, arm_counts = Counter(), Counter(), Counter(), Counter()
    prompts, decisions, outcomes, samples = {}, {}, {}, {}

    with (directory / 'wire.jsonl').open('x') as wire:
        def dispatch(task, arm, role, instruction, inputs, *, repeat=None):
            counts[role] += 1
            if counts[role] > frozen['logicalLimitsByRole'].get(role, 0):
                raise grounded.ResponderFailed from ValueError('The comparison exceeded a sealed role limit')
            limits = {'evaluation': grounded.METRIC_LIMIT,
                      'reflection': 1 if arm == 'shared' else (3 if arm == 'cpo' else grounded.REFLECTION_LIMIT),
                      'admission': 2 * SPLITS['admission'] * grounded.REPEATS}
            arm_counts[task, arm, role] += 1
            if role in limits and arm_counts[task, arm, role] > limits[role]:
                raise grounded.ResponderFailed from ValueError('An arm exceeded its per-task role limit')
            if role != 'qualification':
                costs[arm] += 1
            request = {'task': task, 'role': role, 'instruction': instruction, 'input': inputs}
            if role != 'reflection':
                request['jsonSchema'] = schema(groups[task])
            if repeat is not None:
                request['repeat'] = repeat
            key = json.dumps(request, sort_keys=True, separators=(',', ':'))
            if role != 'reflection' and key in samples:
                return samples[key]
            physical[role] += 1
            sequence = sum(physical.values())
            record(wire, {'sequence': sequence, 'arm': arm, 'request': request})
            try:
                text = respond(deepcopy(request))
                if not isinstance(text, str):
                    raise ValueError('The responder must return text')
            except Exception as error:
                raise grounded.ResponderFailed from error
            record(wire, {'sequence': sequence, 'response': text})
            if role != 'reflection':
                samples[key] = text
            return text

        try:
            if prior is None:
                for task, task_groups in groups.items():
                    prompts[task], decisions[task] = choose(
                        task, task_groups, lambda *args, **kw: dispatch(task, *args, **kw),
                        certify_final_draft=certify_final_draft, certify_opening=certify_opening)
            else:
                prompts, decisions = prior['selected'], prior['admissionDecisions']
            split = 'holdout' if prior is None else 'confirmation'
            for task, task_groups in groups.items():
                paired = grounded.qualify_task(task, task_groups[split], prompts[task],
                                               lambda *args, **kw: dispatch(task, *args, **kw))
                outcomes[task] = [{'id': row_id, 'repeat': repeat, 'critical': critical, 'passes': passes}
                                  for (row_id, repeat), (critical, passes) in paired.items()]
        except grounded.ResponderFailed as error:
            raise error.__cause__ from None

    costs = ({arm: costs[arm] + costs['shared'] for arm in ARMS} if prior is None else prior['searchCallsByArm'])
    result = {'planSha256': seal, 'delivery': delivery, 'logicalCallsByRole': dict(counts),
              'physicalCallsByRole': dict(physical), 'searchCallsByArm': costs, 'selected': prompts,
              'admissionDecisions': decisions, 'holdout': outcomes, 'outcome': grade(outcomes, costs, frozen['gate'])}
    save(directory / 'result.json', result)
    return result


def replay(directory, fresh, *, development=None, certify_final_draft=None, certify_opening=None):
    if fresh.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Replay requires a separate archive outside its source directory')
    saved = grounded.load_json((directory / 'plan.json').read_bytes())
    if certify_final_draft is None:
        certify_final_draft = saved.get('certifyFinalDraft', False)
    if certify_opening is None:
        certify_opening = saved.get('certifyOpening', False)
    seal = saved.get('planSha256')
    delivery = saved.get('delivery')
    pending = iter((directory / 'wire.jsonl').read_bytes().splitlines())
    sequence = 0

    def respond(request):
        nonlocal sequence
        sequence += 1
        start, finish = (grounded.load_json(next(pending, b'null')) for _ in range(2))
        if (not isinstance(start, dict) or not isinstance(finish, dict) or start.get('request') != request or
                start.get('sequence') != sequence or finish.get('sequence') != sequence):
            raise ValueError('The wire journal ended early or differs from the replayed request')
        return finish.get('response')

    result = run(seal, fresh, respond, delivery=delivery, development=development,
                 certify_final_draft=certify_final_draft, certify_opening=certify_opening)
    if next(pending, None) is not None or any((directory / name).read_bytes() != (fresh / name).read_bytes()
                                             for name in ARCHIVE_FILES):
        raise ValueError('The replayed archive differs from the saved results')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--fixture', metavar='PLAN_SHA256')
    modes.add_argument('--replay', type=Path)
    parser.add_argument('--certify-final-draft', action='store_true',
                        help='Use the separately sealed exact final-draft validation protocol')
    parser.add_argument('--certify-opening', action='store_true',
                        help='Enable the separately sealed exact opening rewrite certificate')
    parser.add_argument('--development', type=Path, help='Bind an independent panel to this development archive')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if bool(args.fixture or args.replay) != bool(args.out) or (args.out and args.out.exists()):
        parser.error('Fixture and replay require a fresh --out archive')
    if args.fixture:
        from benchmarks.grounded_staged_fixture import respond

        result = run(args.fixture, args.out, respond, delivery='fixture', development=args.development,
                     certify_final_draft=args.certify_final_draft, certify_opening=args.certify_opening)
    elif args.replay:
        result = replay(args.replay, args.out, development=args.development,
                        certify_final_draft=True if args.certify_final_draft else None,
                        certify_opening=True if args.certify_opening else None)
    else:
        _, frozen, _ = prepare(args.development, certify_final_draft=args.certify_final_draft,
                               certify_opening=args.certify_opening)
        result = {**frozen, 'planSha256': digest(frozen)}
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
