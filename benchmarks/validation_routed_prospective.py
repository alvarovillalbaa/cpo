"""Rehearse an independent comparison of the validation-routed CPO policy."""

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import full_roster_precheck_prospective as prior
from benchmarks.settled_episode_prospective_fixture import responder
from cpo import Observation
from cpo._contract import digest
from cpo.full_roster_precheck import run_full_roster_feedback_episode
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode


parent = prior.parent
ADAPTIVE = prior.CANDIDATE
CANDIDATE = 'cpo-validation-routed'
CONTROLS = (parent.SETTLED, ADAPTIVE, *parent.witness.GEPA)
ARM_RUNNERS = {parent.SETTLED: parent.run_settled_episode, ADAPTIVE: run_full_roster_feedback_episode}
BASE_SHA = prior.PARENT_SHA
ARCHIVE_SHA = '5b461240dec45149ef92e912f615a5f12b34d0ca5a8a637fa71c60e3d81607d8'
_CHOOSE = parent.choose
_GRADE = parent.staged.grade
AUDIT_FILE = 'routing-audit.json'


def prepare():
    tasks, base = parent.prepare()
    frozen = prior.locked('settled-episode-prospective-plan-v1.json', BASE_SHA)
    base_seal = frozen.pop('planSha256')
    if digest(base) != digest(frozen) or digest(base) != base_seal:
        raise ValueError('The original paired comparison must reproduce')
    evidence = prior.locked('validation-routed-opening-v1.json', ARCHIVE_SHA)
    if digest(evidence['plan']) != evidence['planSha256']:
        raise ValueError('Use the exact archived routing evidence')

    arms = (*CONTROLS, CANDIDATE)
    limits = Counter(base['physicalLimitsByRole'])
    cycles = len(tasks) * parent.CYCLES
    limits.update(evaluation=cycles * parent.CPO_CAP, admission=cycles * 2 * parent.ADMISSION,
                  qualification=sum(len(groups['holdout']) for groups in tasks.values()) * parent.grounded.REPEATS)
    paths = ('benchmarks/validation_routed_prospective.py', 'benchmarks/full_roster_precheck_prospective.py', 'pyproject.toml',
             'cpo/full_roster_precheck/__init__.py', 'cpo/full_roster_precheck/fixed_opening.py',
             'cpo/full_roster_precheck/validation_routing.py', 'benchmarks/grounded_staged_policy_comparison.py')
    sources = {name: sha256((parent.ROOT / name).read_bytes()).hexdigest() for name in paths}
    return tasks, {**base, 'protocol': 'cpo-validation-routed-prospective-v1', 'candidate': CANDIDATE,
                   'arms': arms, 'controls': CONTROLS, 'openingTrainingProbes': 0,
                   'openingTrainingProbesByArm': dict.fromkeys(ARM_RUNNERS, 2) | {CANDIDATE: 0},
                   'perCycleSearchCaps': dict.fromkeys((*ARM_RUNNERS, CANDIDATE), parent.CPO_CAP)
                   | dict.fromkeys(parent.witness.GEPA, parent.GEPA_CAP),
                   'baseManifestSha256': BASE_SHA, 'basePlanSha256': base_seal,
                   'archiveEvidenceSha256': ARCHIVE_SHA, 'archiveEvidencePlanSha256': evidence['planSha256'],
                   'sourceSha256': {**base['sourceSha256'], **sources},
                   'logicalLimitsByRole': dict(limits), 'physicalLimitsByRole': dict(limits),
                   'requestCeiling': sum(limits.values()), 'delivery': 'fixture-rehearsal-only',
                   'sharingRule': ('Draft once. Each arm nominates and qualifies independently. '
                                   'Reuse only exact role-, task-, case-, prompt-, and repeat-matched requests. '
                                   'Score each distinct selected prompt and the initial prompt on every holdout repeat. '
                                   'Gate against all four comparators on logical and attributed search costs.')}


def choose(task, groups, dispatch, journal):
    cycles, blocks, drafts = parent.draft_cycles(task, groups, dispatch, journal)
    with patch.multiple(parent, draft_cycles=lambda *_: (cycles, blocks, drafts), ARMS=CONTROLS):
        selected, decisions, rosters = _CHOOSE(task, groups, dispatch, journal)
    cases = {row['id']: row for split in ('validation', 'admission') for row in groups[split]}

    def grade(prompt, row, role, repeat=None):
        spec = cases[row.id]
        reply = dispatch(CANDIDATE, role, prompt, spec['input'], repeat=repeat)
        return parent.grounded.score(reply, spec['expected'])[0]

    before = len(journal.search_uses[CANDIDATE])
    result = run_validation_routed_episode(
        parent.grounded.BASELINE, cycles, lambda prompt, row: Observation(grade(prompt, row, 'evaluation'), {}),
        qualify=lambda prompt, row, repeat: grade(prompt, row, 'admission', repeat),
    )
    if (result.training_evaluations or result.evaluations != len(journal.search_uses[CANDIDATE]) - before
            or any(step.search.evaluations > parent.CPO_CAP
                   or step.qualification_evaluations > 2 * parent.ADMISSION for step in result.cycles)):
        raise ValueError('The routed arm must reconcile every lookup and obey its per-cycle budget')
    journal.search_uses[CANDIDATE].extend(drafts)
    selected[CANDIDATE] = result.prompt
    decisions[CANDIDATE] = [
        {'schedule': schedule, 'nominee': step.search.finalist, 'prompt': step.prompt,
         'admission': step.qualification.status if step.qualification else 'skipped',
         'validationLookups': step.search.evaluations, 'admissionLookups': step.qualification_evaluations}
        for schedule, step in zip(result.cycle_schedules, result.cycles, strict=True)
    ]
    return selected, decisions, rosters


def grade_all(outcomes, costs, gate, *, controls):
    return _GRADE(outcomes, costs, gate, controls=CONTROLS)


@contextmanager
def run_with_plan(tasks, plan):
    with (patch.multiple(parent, prepare=lambda: (tasks, plan), CPO=ARM_RUNNERS,
                         ARMS=plan['arms'], FEEDBACK=CANDIDATE, choose=choose),
          patch.object(parent.staged, 'grade', grade_all)):
        yield


def fixture(tasks):
    respond = responder(tasks)
    easy = {row['input']: row['expected'] for row in tasks['ticket']['validation'][:2]}
    outage = tasks['outage']
    fifth = f"fixture rewrite {outage['train'][2 * (parent.TRAIN // parent.DRAFTS)]['id']}"
    opening = {row['input']: row['expected'] for row in outage['validation'][:parent.VALIDATION]}
    admission = {row['input']: row['expected'] for row in outage['admission'][:parent.ADMISSION]}

    def reply(request):
        if (request['task'] == 'ticket' and request['role'] == 'evaluation'
                and request['instruction'] == parent.grounded.BASELINE and request['input'] in easy):
            return json.dumps(easy[request['input']], sort_keys=True)
        if request['task'] == 'outage':
            role, prompt, inputs = (request[key] for key in ('role', 'instruction', 'input'))
            if role == 'evaluation' and inputs in opening:
                return json.dumps(opening[inputs] if prompt == fifth else {}, sort_keys=True)
            if role == 'admission' and inputs in admission and prompt == fifth:
                return json.dumps(admission[inputs], sort_keys=True)
        return respond(request)

    return reply


def audit(result, directory, tasks):
    if result['delivery'] != 'fixture':
        raise ValueError('This audit requires a fixture archive')
    physical, candidate_only = Counter(), Counter()
    shared, qualification = set(), set()
    for line in (directory / 'wire.jsonl').read_bytes().splitlines():
        item = parent.grounded.load_json(line)
        if 'request' not in item:
            continue
        request = item['request']
        task, role = request['task'], request['role']
        physical[role] += 1
        key = digest(request)
        if role != 'reflection' and key in shared:
            raise ValueError('An identical request was physically sent twice')
        shared.add(key)
        if role == 'qualification':
            qualification.add((task, request['instruction'], request['input'], request['repeat']))
        if item['arm'] == CANDIDATE:
            split = {'evaluation': 'validation', 'admission': 'admission'}.get(role)
            if split is None or request['input'] not in {row['input'] for row in tasks[task][split]}:
                raise ValueError('The routed arm must buy only validation or admission before holdout')
            candidate_only[role] += 1
    expected = {(task, prompt, row['input'], repeat) for task, groups in tasks.items()
                for prompt in set(result['selected'][task].values()) for row in groups['holdout']
                for repeat in range(parent.grounded.REPEATS)}
    if qualification != expected or physical != result['physicalCallsByRole']:
        raise ValueError('Every distinct selected prompt must receive its own full holdout')
    diverged = [task for task in tasks if result['selected'][task][ADAPTIVE] != result['selected'][task][CANDIDATE]]
    return {'candidateOnlyPhysicalSearch': dict(candidate_only), 'differentPromptsFromAdaptive': diverged,
            'holdoutRequests': len(expected), 'providerRequests': 0}


def run_fixture(seal, directory):
    tasks, plan = prepare()
    with run_with_plan(tasks, plan):
        result = parent.run(seal, directory, fixture(tasks), delivery='fixture')
    verdict = audit(result, directory, tasks)
    parent.staged.save(directory / AUDIT_FILE, verdict)
    return result, verdict


def replay(directory, fresh):
    source = parent.grounded.load_json((directory / 'plan.json').read_bytes())
    if source['delivery'] != 'fixture':
        raise ValueError('This rehearsal only replays fixture archives')
    expected = (directory / AUDIT_FILE).read_bytes()
    tasks, plan = prepare()
    with run_with_plan(tasks, plan):
        result = parent.replay(directory, fresh)
    verdict = audit(result, fresh, tasks)
    parent.staged.save(fresh / AUDIT_FILE, verdict)
    if expected != (fresh / AUDIT_FILE).read_bytes():
        raise ValueError('The routing audit differs from the original archive')
    return result, verdict


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument('--fixture', metavar='PLAN_SHA256')
    mode.add_argument('--replay', type=Path)
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    _, plan = prepare()
    if not args.fixture and not args.replay and not args.out:
        print(json.dumps({**plan, 'planSha256': digest(plan)}, indent=2, sort_keys=True))
        return
    if args.out is None or args.out.exists() or not (args.fixture or args.replay):
        cli.error('Rehearsal requires a seal or fixture archive and a fresh output path')
    if args.replay:
        replay(args.replay, args.out)
    else:
        run_fixture(args.fixture, args.out)


if __name__ == '__main__':
    main()
