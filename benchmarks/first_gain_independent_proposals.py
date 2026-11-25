"""Rehearse a matched comparison in which each optimizer drafts its own prompts."""

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import certified_nomination_prospective as shared, pool
from benchmarks.gepa_disjoint_cases import CaseRows
from cpo import Observation
from cpo._contract import digest
from cpo.full_roster_precheck.first_gain import run_first_gain_episode
from cpo.paired_qualification import certify_paired_qualification
from cpo.settled_episode import EpisodeCycle


parent = shared.parent
grounded, staged = parent.grounded, parent.staged
FIRST, HALVING = 'cpo-first-gain', 'successive-halving'
CONTROLS = (shared.CERTIFIED, HALVING, *parent.witness.GEPA)
ARMS = (FIRST, *CONTROLS)
VALIDATION, ADMISSION, TRAIN, CYCLES = parent.VALIDATION, parent.ADMISSION, parent.TRAIN, parent.CYCLES
DRAFT_CAP, PROBES, GEPA_CAP = 2, grounded.MINIBATCH, parent.GEPA_CAP
SCREEN_CAP = parent.CPO_CAP + PROBES
AUDIT = 'independent-proposals-audit.json'
PARITY = 'e925474dbc13eb4564f5645a856ae313a7bcb50309cbe5636c4ecd63bbc0e585'
PRIOR_PLAN = 'a0c1e4f73ef9d286598bbba9ff0973df46fb755eab16d1a489afa3212a5e7cbe'
_GRADE = staged.grade


def training_row(row):
    return {key: row[key] for key in ('id', 'input', 'expected')}


def prepare():
    tasks, base = shared.prepare()
    parity = shared.prior.prior.locked('first-gain-episode-parity-v1.json', PARITY)
    if digest(base) != PRIOR_PLAN or digest(parity['plan']) != parity['planSha256']:
        raise ValueError('Use the exact published prospective plan and first-gain parity receipt')
    api = 'cpo/full_roster_precheck/first_gain.py'
    paths = (api, 'benchmarks/first_gain_independent_proposals.py', 'benchmarks/opening_screen_typed.py',
             'benchmarks/pool.py')
    sources = {name: sha256((parent.ROOT / name).read_bytes()).hexdigest() for name in paths}
    if parity['plan']['sources'][api] != sources[api]:
        raise ValueError('Use the first-gain policy verified against the archived benchmarks')
    for groups in tasks.values():
        rows = [row for panel in groups.values() for row in panel]
        if len({row['id'] for row in rows}) != len(rows) or len({row['input'] for row in rows}) != len(rows):
            raise ValueError('Training, validation, admission and holdout cases must stay disjoint')
    caps = {FIRST: SCREEN_CAP, shared.CERTIFIED: SCREEN_CAP, HALVING: SCREEN_CAP,
            **dict.fromkeys(parent.witness.GEPA, GEPA_CAP)}
    cycles = len(tasks) * CYCLES
    limits = {'reflection': cycles * DRAFT_CAP * len(ARMS), 'evaluation': cycles * sum(caps.values()),
              'admission': cycles * len(ARMS) * 2 * ADMISSION,
              'qualification': (len(ARMS) + 1) * grounded.REPEATS * sum(len(group['holdout']) for group in tasks.values())}
    return tasks, {**base, 'protocol': 'cpo-first-gain-independent-proposals-v1', 'candidate': FIRST, 'arms': ARMS,
                   'controls': CONTROLS, 'perCycleSearchCaps': caps, 'draftsPerCycle': DRAFT_CAP,
                   'openingTrainingProbesByArm': {FIRST: PROBES, shared.CERTIFIED: PROBES, HALVING: PROBES},
                   'previousPlanSha256': PRIOR_PLAN, 'firstGainParityReceiptSha256': PARITY,
                   'sourceSha256': {**base['sourceSha256'], **sources}, 'physicalLimitsByRole': limits,
                   'logicalLimitsByRole': limits, 'requestCeiling': sum(limits.values()),
                   'delivery': 'fixture-rehearsal-only', 'qualificationOrder': 'independent-paired',
                   'proposalRule': ('Every arm drafts independently from its own enrolled parents and paid training '
                                    'feedback. All arms can buy up to two single-proposal reflections per cycle. '
                                    'GEPA chooses its training minibatches and proposal parents.'),
                   'sharingRule': ('Reflection requests are always charged to the generating arm. Reuse only exact '
                                   'evaluation, admission or holdout requests. Every distinct deployed prompt and '
                                   'the initial prompt receive the complete paired holdout.'),
                   'caseRule': ('Use the same cycle assignments and graders. Start each CPO cycle by routing '
                                'from the arm’s current incumbent. Admission and holdout retain critical labels.')}


def native(start, train, validation, observe, draft, *, seed, batched, paid):
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, TrackingConfig, optimize_anything
    from gepa.strategies.proposal_sampling import SameParentSampling
    from gepa.utils.stop_condition import ScoreThresholdStopper

    width = 2 if batched else 1

    def metric(prompt, example):
        return float(observe(prompt, example).passed)

    def propose(candidate, _observations, components):
        component, = components
        source = candidate[component]
        return {component: draft(source, grounded.UPDATE) or source}

    config = GEPAConfig(
        engine=EngineConfig(seed=seed, parallel=False, use_cloudpickle=False, cache_evaluation=True,
                            max_metric_calls=GEPA_CAP, max_candidate_proposals=DRAFT_CAP // width,
                            track_best_outputs=False, sampling_strategy=SameParentSampling(width) if batched else None),
        reflection=ReflectionConfig(reflection_lm=None, custom_candidate_proposer=propose,
                                    reflection_minibatch_size=PROBES),
        tracking=TrackingConfig(logger=grounded.GepaLogger()),
        stop_callbacks=[ScoreThresholdStopper(1.0),
                        lambda _: len(paid) + width * (2 * PROBES + len(validation)) > GEPA_CAP],
    )
    return optimize_anything(start, evaluator=metric, dataset=CaseRows(train), valset=CaseRows(validation),
                             config=config).best_candidate


def cycle(task, arm, incumbent, train, validation, admission, dispatch, journal, seen, seed):
    allowed = {row['id']: row for row in (*train, *validation, *admission)}
    training = {row['id']: training_row(row) for row in train}
    search_ids = training.keys() | {row['id'] for row in validation}
    proof_ids = {row['id'] for row in admission}
    cap = GEPA_CAP if arm in parent.witness.GEPA else SCREEN_CAP
    paid, roster, attempts = {}, [], 0
    before = len(journal.search_uses[arm])

    def observe(prompt, spec):
        case = spec['id']
        key = prompt, case
        if prompt not in (incumbent, *roster) or case not in search_ids or allowed[case] != spec:
            raise ValueError('A search lookup left its enrolled roster or current case split')
        if key not in paid:
            if len(paid) == cap:
                raise ValueError('The cycle exceeded its evaluation cap')
            text = dispatch(arm, 'evaluation', prompt, spec['input'])
            passed, fields = grounded.score(text, spec['expected'])
            paid[key] = Observation(passed, {'id': case, 'observed': text}, fields)
        return paid[key]

    def qualify(prompt, row, repeat):
        if row.id not in proof_ids or prompt not in (incumbent, *roster) or repeat != 0:
            raise ValueError('An admission lookup left its enrolled roster or independent panel')
        spec = allowed[row.id]
        text = dispatch(arm, 'admission', prompt, spec['input'], repeat=repeat)
        return grounded.score(text, spec['expected'])[0]

    def draft(source, instruction):
        nonlocal attempts
        if attempts == DRAFT_CAP or source not in (incumbent, *roster):
            raise ValueError('Reflection exceeded its allowance or used a foreign parent')
        attempts += 1
        feedback = [reply.feedback for (prompt, case), reply in paid.items() if prompt == source and case in training]
        request = {'task': task, 'current': source, 'labeledTraining': list(training.values()),
                   'recentFeedback': feedback[-PROBES:]}
        reply = dispatch(arm, 'reflection', instruction, request)
        proposals = grounded.proposals(reply, source, ('instruction',))
        if proposals and proposals[0] not in seen:
            proposal, = proposals
            seen.add(proposal)
            roster.append(proposal)
            return proposal
        return None

    val_rows, proof_rows = staged.cases(task, validation), staged.cases(task, admission)
    if arm in parent.witness.GEPA:
        nominee = native(incumbent, train, validation, observe, draft, seed=seed,
                         batched=arm == parent.witness.GEPA[-1], paid=paid)
        schedule = arm
    else:
        for row in train[:PROBES]:
            observe(incumbent, row)
        for instruction in ('Propose a complete rewrite.', 'Propose a focused repair.'):
            draft(incumbent, f'{grounded.UPDATE} {instruction}')
        if arm == HALVING:
            by_id = {row['id']: row for row in validation}
            nominee = pool.successive_halving((incumbent, *roster), tuple(by_id),
                                             lambda p, i: observe(p, by_id[i]).passed, parent.CPO_CAP)
            schedule = HALVING
        else:
            runner = run_first_gain_episode if arm == FIRST else shared.run_certified_nomination_episode
            result = runner(incumbent, (EpisodeCycle(tuple(roster), tuple(val_rows), tuple(proof_rows), seed),),
                            lambda p, row: observe(p, allowed[row.id]), qualify=qualify)
            step, = result.cycles
            nominee, proof, schedule = step.search.finalist or incumbent, step.qualification, result.schedule
            if result.evaluations + PROBES != len(paid) + step.qualification_evaluations:
                raise ValueError('CPO cycle callbacks must reconcile including its training probes')
    if arm in (*parent.witness.GEPA, HALVING):
        proof = certify_paired_qualification(incumbent, nominee, proof_rows, qualify, seed=seed)
    proof_reads = len(proof.observations) if proof else 0
    deployed = proof.prompt if proof else incumbent
    if (nominee not in (incumbent, *roster) or deployed not in (incumbent, nominee)
            or len(paid) + attempts + proof_reads != len(journal.search_uses[arm]) - before):
        raise ValueError('Each cycle must reconcile its drafts, lookups and qualified deployment')
    return {'start': incumbent, 'nominee': nominee, 'prompt': deployed, 'schedule': schedule,
            'admission': proof.status if proof else 'skipped', 'drafts': attempts, 'roster': roster,
            'evaluations': len(paid), 'admissionLookups': proof_reads}


def choose(task, groups, dispatch, journal):
    selected, decisions, sizes = {'initial': grounded.BASELINE}, {}, {}
    order = list(ARMS)
    Random(f'{parent.SEED}:{task}').shuffle(order)
    for arm in order:
        incumbent = grounded.BASELINE
        seen, steps = {incumbent}, []
        for index in range(CYCLES):
            width = (TRAIN, VALIDATION, ADMISSION)
            panels = [groups[role][index * size:(index + 1) * size]
                      for role, size in zip(('train', 'validation', 'admission'), width, strict=True)]
            decision = cycle(task, arm, incumbent, *panels, dispatch, journal, seen, parent.SEED + index)
            steps.append(decision)
            incumbent = decision['prompt']
        selected[arm], decisions[arm] = incumbent, steps
        sizes[arm] = [len(step['roster']) for step in steps]
    return selected, decisions, sizes


def grade_all(outcomes, costs, gate, *, controls):
    return _GRADE(outcomes, costs, gate, controls=CONTROLS)


@contextmanager
def configured(tasks, plan):
    with (patch.multiple(parent, prepare=lambda: (tasks, plan), ARMS=ARMS, FEEDBACK=FIRST, choose=choose),
          patch.object(staged, 'grade', grade_all)):
        yield


def fixture(tasks):
    rows = {task: {row['input']: row['expected'] for panel in groups.values() for row in panel}
            for task, groups in tasks.items()}
    panel = {task: {row['input']: index // width
                    for role, width in (('train', TRAIN), ('validation', VALIDATION), ('admission', ADMISSION))
                    for index, row in enumerate(groups[role])} for task, groups in tasks.items()}
    first_train = {task: {groups['train'][index * TRAIN]['id']: index for index in range(CYCLES)}
                   for task, groups in tasks.items()}
    harder_validation = tasks['warehouse']['validation'][0]['input']
    created, serial = {}, 0

    def respond(request):
        nonlocal serial
        task, role, prompt, inputs = (request[key] for key in ('task', 'role', 'instruction', 'input'))
        if role == 'reflection':
            serial += 1
            index = first_train[task][inputs['labeledTraining'][0]['id']]
            proposal = f'fixture {task} draft {serial:03}'
            weak = (task == 'warehouse' and index == 0 and inputs['current'] == grounded.BASELINE
                    and prompt == grounded.UPDATE)
            created[proposal] = index, weak
            return json.dumps({'instruction': proposal}, sort_keys=True)
        index, weak = created.get(prompt, (-1, False))
        passed = index >= 0 and (role == 'qualification' or panel[task][inputs] <= index)
        if role == 'evaluation' and weak and inputs == harder_validation:
            passed = False
        if role == 'admission' and task == 'outage' and index == 0:
            passed = False
        return json.dumps(rows[task][inputs] if passed else {}, sort_keys=True)

    return respond


def audit(tasks, result, directory):
    if result['delivery'] != 'fixture':
        raise ValueError('This rehearsal requires fixture delivery')
    physical, drafts = Counter(), Counter()
    held, requests = set(), set()
    training = {task: [[training_row(row) for row in groups['train'][start:start + TRAIN]]
                       for start in range(0, len(groups['train']), TRAIN)] for task, groups in tasks.items()}
    for line in (directory / 'wire.jsonl').read_bytes().splitlines():
        event = grounded.load_json(line)
        if 'request' not in event:
            continue
        request = event['request']
        task, role = request['task'], request['role']
        physical[role] += 1
        if role == 'reflection':
            inputs = request['input']
            panel = inputs['labeledTraining']
            ids = {case['id'] for case in panel}
            if panel not in training[task] or any(row['id'] not in ids for row in inputs['recentFeedback']):
                raise ValueError('Reflection used a case outside its current training panel')
            drafts[task, event['arm']] += 1
        else:
            key = digest(request)
            if key in requests:
                raise ValueError('An exact case request was charged twice')
            requests.add(key)
        if role == 'qualification':
            held.add((task, request['instruction'], request['input'], request['repeat']))
    matched = {(task, prompt, row['input'], repeat) for task, groups in tasks.items()
               for prompt in set(result['selected'][task].values()) for row in groups['holdout']
               for repeat in range(grounded.REPEATS)}
    declared = Counter({(task, arm): sum(item['drafts'] for item in steps)
                        for task, arms in result['decisions'].items() for arm, steps in arms.items()})
    if matched != held or physical != result['physicalCallsByRole'] or drafts != declared:
        raise ValueError('The independent proposal and paired holdout ledgers must reconcile')
    search_uses = Counter()
    for task, arms in result['decisions'].items():
        all_prompts = set()
        for arm, steps in arms.items():
            incumbent = grounded.BASELINE
            for step in steps:
                if (step['start'] != incumbent
                        or (step['prompt'] != incumbent and step['admission'] != 'promoted')):
                    raise ValueError('Each cycle must start from the preceding qualified deployment')
                incumbent = step['prompt']
                search_uses[arm] += step['drafts'] + step['evaluations'] + step['admissionLookups']
            if result['selected'][task][arm] != incumbent:
                raise ValueError('The holdout must score the final qualified prompt')
            owned = {prompt for step in steps for prompt in step['roster']}
            if owned & all_prompts:
                raise ValueError('The fixture must exercise genuinely distinct rosters')
            all_prompts.update(owned)
    if search_uses != result['searchCosts']['logicalSearchUses']:
        raise ValueError('Every logical search use must reconcile to a cycle')
    return {'draftRequestsByArm': {arm: sum(drafts[task, arm] for task in tasks) for arm in ARMS},
            'holdoutRequests': len(held), 'providerRequests': 0}


def run_fixture(seal, output):
    tasks, plan = prepare()
    with configured(tasks, plan):
        result = parent.run(seal, output, fixture(tasks), delivery='fixture')
    receipt = audit(tasks, result, output)
    staged.save(output / AUDIT, receipt)
    return result, receipt


def replay(source, output):
    manifest = grounded.load_json((source / 'plan.json').read_bytes())
    if manifest.get('delivery') != 'fixture':
        raise ValueError('Only fixture archives can be replayed')
    tasks, plan = prepare()
    with configured(tasks, plan):
        result = parent.replay(source, output)
    receipt = audit(tasks, result, output)
    staged.save(output / AUDIT, receipt)
    if (source / AUDIT).read_bytes() != (output / AUDIT).read_bytes():
        raise ValueError('The proposal audit differs from the original archive')
    return result, receipt


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--fixture', metavar='PLAN_SHA256')
    mode.add_argument('--replay', type=Path)
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    _, plan = prepare()
    if not (args.fixture or args.replay or args.out):
        print(json.dumps({**plan, 'planSha256': digest(plan)}, indent=2, sort_keys=True))
        return
    if args.out is None or args.out.exists() or not (args.fixture or args.replay):
        cli.error('Use a fixture seal or archive and a fresh output directory')
    if args.replay:
        replay(args.replay, args.out)
    else:
        run_fixture(args.fixture, args.out)


if __name__ == '__main__':
    main()
