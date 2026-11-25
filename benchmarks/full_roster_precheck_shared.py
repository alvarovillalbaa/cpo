"""Rehearse the full-roster comparison with a bounded shared-reply journal."""

import argparse
from collections import Counter
from contextlib import contextmanager
from functools import partial
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import full_roster_precheck_prospective as prior
from cpo._contract import digest


parent = prior.parent
REFERENCE, CANDIDATE = prior.REFERENCE, prior.CANDIDATE
PARENT_FILE = 'full-roster-precheck-prospective-plan-v1.json'
PARENT_SHA = '30ece853b23d1770136d5c618fca17df18949fa0ce4cf1efb4049d936be70079'
EXTRA_VALIDATION_PER_CYCLE = 18
_JOURNAL = parent.shared.Journal
_CHOOSE = parent.choose


def prepare():
    tasks, previous = prior.prepare()
    sealed = prior.locked(PARENT_FILE, PARENT_SHA)
    seal = sealed.pop('planSha256')
    if digest(previous) != seal or digest(sealed) != seal:
        raise ValueError('The original five-arm plan must reproduce')
    _, four = parent.prepare()
    limits = dict(four['physicalLimitsByRole'])
    limits['evaluation'] += len(tasks) * parent.CYCLES * EXTRA_VALIDATION_PER_CYCLE
    file = Path(__file__).resolve()
    return tasks, {**previous, 'protocol': 'cpo-full-roster-precheck-shared-v1',
                   'previousPortableSeal': seal, 'previousPortableSha256': PARENT_SHA,
                   'sourceSha256': {**previous['sourceSha256'], str(file.relative_to(parent.ROOT)):
                                    sha256(file.read_bytes()).hexdigest()},
                   'physicalLimitsByRole': limits, 'requestCeiling': sum(limits.values()),
                   'candidateNewValidationLimitPerCycle': EXTRA_VALIDATION_PER_CYCLE,
                   'sharingRule': 'Run all four original arms in their original order before the candidate. '
                                  'Candidate training and admission reuse exact packaged feedback requests. '
                                  'At most 18 candidate-only validation replies fit each cycle. Require '
                                  'matching decisions before holdout, which grades each distinct prompt once.'}


class SharedJournal(_JOURNAL):
    """Enforce the shareable roles before entering the provider dispatcher."""

    def __init__(self, wire, plan, respond, *, tasks):
        super().__init__(wire, plan, respond)
        self.candidate_limit = plan['candidateNewValidationLimitPerCycle']
        self.validation_cycles = {task: {row['input']: index // parent.VALIDATION
                                         for index, row in enumerate(groups['validation'])}
                                  for task, groups in tasks.items()}
        self.reference = set()
        self.candidate_validation = Counter()

    def send(self, arm, request):
        task, role = request['task'], request['role']
        key = json.dumps(request, sort_keys=True, separators=(',', ':'))
        if arm == CANDIDATE:
            cycle = self.validation_cycles[task].get(request['input']) if role == 'evaluation' else None
            if cycle is None:
                if role not in ('admission', 'evaluation') or key not in self.reference:
                    raise parent.grounded.ResponderFailed from ValueError('Candidate must reuse the reference reply')
            elif key not in self.samples:
                slot = task, cycle
                if self.candidate_validation[slot] == self.candidate_limit:
                    raise parent.grounded.ResponderFailed from ValueError('Candidate exceeded its new validation allowance')
                self.candidate_validation[slot] += 1
        reply = super().send(arm, request)
        if arm == REFERENCE and role in ('admission', 'evaluation'):
            self.reference.add(key)
        return reply


class ReferenceFirst(parent.Random):
    def shuffle(self, values):
        if CANDIDATE in values and REFERENCE in values:
            values.remove(CANDIDATE)
            super().shuffle(values)
            values.append(CANDIDATE)
        else:
            super().shuffle(values)


def choose(task, groups, dispatch, journal):
    selected, decisions, rosters = _CHOOSE(task, groups, dispatch, journal)

    def path(arm):
        return [(step['schedule'], step['nominee'], step['prompt']) for step in decisions[arm]]

    if selected[CANDIDATE] != selected[REFERENCE] or path(CANDIDATE) != path(REFERENCE):
        raise ValueError('Candidate and reference must agree before holdout scoring')
    return selected, decisions, rosters


@contextmanager
def run_with_plan(tasks, plan):
    with (prior.run_with_plan(tasks, plan), patch.multiple(parent, choose=choose, Random=ReferenceFirst),
          patch.object(parent.shared, 'Journal', partial(SharedJournal, tasks=tasks))):
        yield


def audit(result, directory, tasks):
    stats = prior.audit(result)
    validation = {task: {row['input']: index // parent.VALIDATION + 1
                         for index, row in enumerate(groups['validation'])} for task, groups in tasks.items()}
    new_replies = Counter()
    for line in (directory / 'wire.jsonl').read_bytes().splitlines():
        event = parent.grounded.load_json(line)
        if event.get('arm') == CANDIDATE:
            request = event['request']
            task = request['task']
            if request['role'] != 'evaluation' or request['input'] not in validation[task]:
                raise ValueError('Candidate-only requests must be validation')
            new_replies[f'{task}/{validation[task][request["input"]]}'] += 1
    return {**stats, 'candidateOnlyPhysicalValidation': dict(new_replies)}


def run_fixture(seal, directory):
    tasks, plan = prepare()
    with run_with_plan(tasks, plan):
        result = parent.run(seal, directory, prior.fixture(tasks), delivery='fixture')
    verdict = audit(result, directory, tasks)
    parent.staged.save(directory / 'feedback-gate.json', verdict)
    return result, verdict


def replay(directory, fresh):
    manifest = parent.grounded.load_json((directory / 'plan.json').read_bytes())
    if manifest['delivery'] != 'fixture':
        raise ValueError('This rehearsal only replays fixture archives')
    expected = (directory / 'feedback-gate.json').read_bytes()
    tasks, plan = prepare()
    with run_with_plan(tasks, plan):
        result = parent.replay(directory, fresh)
    verdict = audit(result, fresh, tasks)
    parent.staged.save(fresh / 'feedback-gate.json', verdict)
    if (fresh / 'feedback-gate.json').read_bytes() != expected:
        raise ValueError('The shared-reply audit differs from its exact replay')
    return result, verdict


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--fixture', metavar='PLAN_SHA256')
    mode.add_argument('--replay', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    _, plan = prepare()
    if not args.fixture and not args.replay and not args.out:
        print(json.dumps({**plan, 'planSha256': digest(plan)}, indent=2, sort_keys=True))
        return
    if args.out is None or args.out.exists() or not (args.fixture or args.replay):
        parser.error('Rehearsal requires a seal or fixture archive and a fresh output path')
    if args.replay:
        replay(args.replay, args.out)
    else:
        run_fixture(args.fixture, args.out)


if __name__ == '__main__':
    main()
