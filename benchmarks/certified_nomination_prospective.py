"""Rehearse a provider-free matched comparison on shared two-challenger rosters."""

import argparse
from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import validation_routed_prospective as prior
from benchmarks.settled_episode_prospective_fixture import responder
from cpo import Observation
from cpo._contract import digest
from cpo.full_roster_precheck.certified_nomination import run_certified_nomination_episode
from cpo.full_roster_precheck.validation_routing import run_validation_routed_episode


parent = prior.parent
CERTIFIED = 'cpo-certified-nomination'
ROUTED = prior.CANDIDATE
NATIVE_AND_SETTLED = (parent.SETTLED, *parent.witness.GEPA)
CONTROLS = (*NATIVE_AND_SETTLED, ROUTED)
ARMS = (*CONTROLS, CERTIFIED)
ROUTED_RUNNERS = {ROUTED: run_validation_routed_episode, CERTIFIED: run_certified_nomination_episode}
PARENT_SHA = '92624df39d1c309fb0b57d71e651ffb100a16685c550f892464504e78db010f2'
PARITY_SHA = '3f634014c9dd4edb9c4676ad0d3734493a22c5e7bfda7f05faf5fba90c0ddcaf'
API_PATH = 'cpo/full_roster_precheck/certified_nomination.py'
AUDIT_FILE = 'certified-nomination-audit.json'
_CHOOSE = parent.choose
_GRADE = parent.staged.grade


def prepare():
    tasks, base = prior.prepare()
    frozen = prior.prior.locked('validation-routed-prospective-plan-v1.json', PARENT_SHA)
    seal = frozen.pop('planSha256')
    if digest(base) != seal or digest(frozen) != seal:
        raise ValueError('The earlier shared-roster plan must reproduce')
    parity = prior.prior.locked('certified-nomination-api-parity-v1.json', PARITY_SHA)
    if digest(parity['plan']) != parity['planSha256']:
        raise ValueError('The package parity receipt must match its plan')
    paths = ('benchmarks/certified_nomination_prospective.py', API_PATH)
    sources = {path: sha256((parent.ROOT / path).read_bytes()).hexdigest() for path in paths}
    if sources[API_PATH] != parity['plan']['sourceSha256'][API_PATH]:
        raise ValueError('Use the packaged policy verified against the archived benchmark')

    cycles = len(tasks) * parent.CYCLES
    caps = dict.fromkeys((parent.SETTLED, *ROUTED_RUNNERS), parent.CPO_CAP) | dict.fromkeys(parent.witness.GEPA, parent.GEPA_CAP)
    limits = {
        'reflection': cycles,
        'evaluation': cycles * sum(caps.values()) + len(tasks) * 2,
        'admission': cycles * len(ARMS) * 2 * parent.ADMISSION,
        'qualification': sum(len(groups['holdout']) for groups in tasks.values()) * len(ARMS) * parent.grounded.REPEATS,
    }
    return tasks, {**base, 'protocol': 'cpo-certified-nomination-prospective-v1', 'candidate': CERTIFIED,
                   'arms': ARMS, 'controls': CONTROLS, 'openingTrainingProbesByArm': {parent.SETTLED: 2, ROUTED: 0, CERTIFIED: 0},
                   'draftsPerCycle': 1, 'maxChallengersPerCycle': 2, 'perCycleSearchCaps': caps,
                   'previousPlanSha256': seal, 'previousPlanReceiptSha256': PARENT_SHA,
                   'packageParityReceiptSha256': PARITY_SHA, 'qualificationOrder': 'paid-rates',
                   'sourceSha256': {**base['sourceSha256'], **sources},
                   'logicalLimitsByRole': limits, 'physicalLimitsByRole': limits,
                   'requestCeiling': sum(limits.values()), 'delivery': 'fixture-rehearsal-only',
                   'proposalRule': ('Draft one rewrite and repair per cycle from its sixteen labeled cases. '
                                    'Drop the pair if its texts repeat the incumbent or any earlier accepted draft. '
                                    'Use the same ordered roster for every arm.'),
                   'sharingRule': ('Reuse only an exact task, role, prompt, case and repeat match. Require identical '
                                   'schedule, nominee, and deployment between routed arms before holdout. Score '
                                   'every distinct final prompt and the initial prompt on the full paired holdout. '
                                   'Compare against both GEPA modes, settled CPO and uncapped routing on both search tallies.')}


def choose(task, groups, dispatch, journal):
    cycles, blocks, drafts = parent.draft_cycles(task, groups, dispatch, journal)
    with patch.multiple(parent, draft_cycles=lambda *_: (cycles, blocks, drafts), ARMS=NATIVE_AND_SETTLED):
        selected, decisions, rosters = _CHOOSE(task, groups, dispatch, journal)
    if any(size not in (0, 2) for size in rosters):
        raise ValueError('Each shared roster must contain either a complete pair or no challengers')
    cases = {row['id']: row for split in ('validation', 'admission') for row in groups[split]}

    for arm, runner in ROUTED_RUNNERS.items():
        def grade(prompt, row, role, repeat=None):
            spec = cases[row.id]
            reply = dispatch(arm, role, prompt, spec['input'], repeat=repeat)
            return parent.grounded.score(reply, spec['expected'])[0]

        before = len(journal.search_uses[arm])
        result = runner(parent.grounded.BASELINE, cycles,
                        lambda prompt, row: Observation(grade(prompt, row, 'evaluation'), {}),
                        qualify=lambda prompt, row, repeat: grade(prompt, row, 'admission', repeat))
        if (result.training_evaluations or result.evaluations != len(journal.search_uses[arm]) - before
                or any(step.search.evaluations > parent.CPO_CAP
                       or step.qualification_evaluations > 2 * parent.ADMISSION for step in result.cycles)):
            raise ValueError('Each routed arm must reconcile its journal and cycle budgets')
        journal.search_uses[arm].extend(drafts)
        selected[arm] = result.prompt
        decisions[arm] = [
            {'schedule': schedule, 'nominee': step.search.finalist, 'prompt': step.prompt,
             'admission': step.qualification.status if step.qualification else 'skipped',
             'validationLookups': step.search.evaluations, 'admissionLookups': step.qualification_evaluations}
            for schedule, step in zip(result.cycle_schedules, result.cycles, strict=True)
        ]

    identity = ('schedule', 'nominee', 'prompt', 'admission')
    paths = zip(decisions[ROUTED], decisions[CERTIFIED], strict=True)
    if selected[ROUTED] != selected[CERTIFIED] or any(
            baseline[key] != candidate[key] for baseline, candidate in paths for key in identity):
        raise ValueError('Certified nomination must preserve the full routed decision before holdout')
    return selected, decisions, rosters


def grade_all(outcomes, costs, gate, *, controls):
    return _GRADE(outcomes, costs, gate, controls=CONTROLS)


@contextmanager
def configured(tasks, plan):
    with (patch.multiple(parent, prepare=lambda: (tasks, plan), DRAFTS=1,
                         CPO={parent.SETTLED: parent.run_settled_episode}, ARMS=ARMS, FEEDBACK=CERTIFIED, choose=choose),
          patch.object(parent.staged, 'grade', grade_all)):
        yield


def fixture(tasks):
    respond = responder(tasks)
    ticket_opening = {row['input']: row['expected'] for row in tasks['ticket']['validation'][:2]}
    outage = {row['input']: row['expected'] for split in ('validation', 'admission') for row in tasks['outage'][split]}

    def reply(request):
        task, role, prompt, inputs = (request[key] for key in ('task', 'role', 'instruction', 'input'))
        if (task == 'ticket' and role == 'evaluation' and prompt == parent.grounded.BASELINE
                and inputs in ticket_opening):
            return json.dumps(ticket_opening[inputs], sort_keys=True)
        if task == 'outage' and role in ('evaluation', 'admission') and inputs in outage:
            passed = prompt.startswith('fixture rewrite ')
            return json.dumps(outage[inputs] if passed else {}, sort_keys=True)
        return respond(request)

    return reply


def audit(result, directory, tasks):
    if result['delivery'] != 'fixture':
        raise ValueError('This audit requires a fixture archive')
    physical, saved = Counter(), Counter()
    unique, holdout = set(), set()
    for line in (directory / 'wire.jsonl').read_bytes().splitlines():
        event = parent.grounded.load_json(line)
        if 'request' not in event:
            continue
        request = event['request']
        task, role = request['task'], request['role']
        physical[role] += 1
        key = digest(request)
        if role != 'reflection' and key in unique:
            raise ValueError('An identical case request was physically charged twice')
        unique.add(key)
        if role == 'qualification':
            holdout.add((task, request['instruction'], request['input'], request['repeat']))
        if event['arm'] in ROUTED_RUNNERS:
            split = {'evaluation': 'validation', 'admission': 'admission'}.get(role)
            if split is None or request['input'] not in {row['input'] for row in tasks[task][split]}:
                raise ValueError('A routed arm may only buy validation and admission search replies')

    expected = {(task, prompt, row['input'], repeat) for task, groups in tasks.items()
                for prompt in set(result['selected'][task].values()) for row in groups['holdout']
                for repeat in range(parent.grounded.REPEATS)}
    if holdout != expected or physical != result['physicalCallsByRole']:
        raise ValueError('Every distinct selected prompt requires its full assigned holdout')
    if physical['reflection'] != len(tasks) * parent.CYCLES:
        raise ValueError('Share exactly one draft pair request in each cycle')

    for decision in result['decisions'].values():
        for baseline, candidate in zip(decision[ROUTED], decision[CERTIFIED], strict=True):
            saved['validationLookupsSaved'] += baseline['validationLookups'] - candidate['validationLookups']
            saved['admissionLookupsSaved'] += baseline['admissionLookups'] - candidate['admissionLookups']
            saved['differentValidationCharges'] += baseline['validationLookups'] != candidate['validationLookups']
    for tally in result['searchCosts'].values():
        if tally[ROUTED] - tally[CERTIFIED] != saved['validationLookupsSaved'] + saved['admissionLookupsSaved']:
            raise ValueError('The paired routing costs must reconcile with the shared draft charges')
    return {'routingComparison': saved, 'holdoutRequests': len(expected), 'providerRequests': 0}


def run_fixture(seal, directory):
    tasks, plan = prepare()
    with configured(tasks, plan):
        result = parent.run(seal, directory, fixture(tasks), delivery='fixture')
    verification = audit(result, directory, tasks)
    parent.staged.save(directory / AUDIT_FILE, verification)
    return result, verification


def replay(directory, fresh):
    manifest = parent.grounded.load_json((directory / 'plan.json').read_bytes())
    if manifest['delivery'] != 'fixture':
        raise ValueError('Only fixture archives can be replayed here')
    expected = (directory / AUDIT_FILE).read_bytes()
    tasks, plan = prepare()
    with configured(tasks, plan):
        result = parent.replay(directory, fresh)
    verification = audit(result, fresh, tasks)
    parent.staged.save(fresh / AUDIT_FILE, verification)
    if expected != (fresh / AUDIT_FILE).read_bytes():
        raise ValueError('The nomination audit differs from the original archive')
    return result, verification


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
