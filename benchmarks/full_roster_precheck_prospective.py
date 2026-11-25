"""Rehearse the full-roster precheck candidate against packaged CPO and GEPA."""

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import settled_episode_prospective as parent
from benchmarks.settled_episode_prospective_fixture import responder
from cpo._contract import digest
from cpo.full_roster_precheck import run_full_roster_feedback_episode


REFERENCE = 'cpo-feedback'
CANDIDATE = 'cpo-full-roster-precheck'
PARENT_SHA = '02cb91d6c9bcceee4afa6d0ebd40cb8926a19b32feac756eabc6e723b2c2c65d'
ARCHIVE_SHA = 'ccca599198358099e47ad35f8a88ceec566b9583e2dd3aa01af2ad534f80af1a'


def locked(name, checksum):
    raw = (parent.ROOT / 'docs' / name).read_bytes()
    if sha256(raw).hexdigest() != checksum:
        raise ValueError(f'Use the original {name}')
    return json.loads(raw)


def prepare():
    tasks, previous = parent.prepare()
    sealed = locked('settled-episode-prospective-plan-v1.json', PARENT_SHA)
    previous_seal = sealed.pop('planSha256')
    if digest(sealed) != previous_seal or digest(previous) != previous_seal:
        raise ValueError('The original prospective plan must reproduce')
    archive = locked('witness-nomination-cost-v1.json', ARCHIVE_SHA)
    if digest(archive['plan']) != archive['planSha256']:
        raise ValueError('Use the original archive evidence')
    extra = {'evaluation': len(tasks) * (parent.CYCLES * parent.CPO_CAP + 2),
             'admission': len(tasks) * parent.CYCLES * parent.ADMISSION * 2,
             'qualification': sum(len(groups['holdout']) for groups in tasks.values()) * parent.grounded.REPEATS}
    limits = {role: count + extra.get(role, 0) for role, count in previous['physicalLimitsByRole'].items()}
    files = (Path(__file__).resolve(), parent.ROOT / 'pyproject.toml',
             parent.ROOT / 'cpo/full_roster_precheck/__init__.py')
    sources = {str(file.relative_to(parent.ROOT)): sha256(file.read_bytes()).hexdigest() for file in files}
    return tasks, {**previous, 'protocol': 'cpo-full-roster-precheck-comparison-v1',
                   'parentPlanSha256': previous_seal, 'parentManifestSha256': PARENT_SHA,
                   'archiveEvidenceSha256': ARCHIVE_SHA, 'sourceSha256': {**previous['sourceSha256'], **sources},
                   'arms': (*previous['arms'], CANDIDATE), 'candidate': CANDIDATE,
                   'perCycleSearchCaps': {**previous['perCycleSearchCaps'], CANDIDATE: parent.CPO_CAP},
                   'logicalLimitsByRole': limits, 'physicalLimitsByRole': limits, 'requestCeiling': sum(limits.values()),
                   'feedbackGate': 'Match every packaged feedback nominee, selected prompt, and holdout grade. '
                                   'Use fewer logical and attributed search requests.',
                   'delivery': 'fixture-rehearsal-only'}


@contextmanager
def run_with_plan(tasks, plan):
    arms = {**parent.CPO, CANDIDATE: run_full_roster_feedback_episode}
    with patch.multiple(parent, CPO=arms, ARMS=plan['arms'], FEEDBACK=CANDIDATE, prepare=lambda: (tasks, plan)):
        yield


def audit(result):
    same_choices = True
    for arms in result['decisions'].values():
        def choices(name):
            return [(step['schedule'], step['nominee'], step['prompt']) for step in arms[name]]

        same_choices &= choices(REFERENCE) == choices(CANDIDATE)
    same_grades = all(row['passes'][REFERENCE] == row['passes'][CANDIDATE]
                      for panel in result['holdout'].values() for row in panel)
    savings = {name: spent[REFERENCE] - spent[CANDIDATE] for name, spent in result['searchCosts'].items()}
    feedback_gate = same_choices and same_grades and all(saved > 0 for saved in savings.values())
    return {'sameFeedbackChoices': same_choices, 'sameFeedbackHoldoutGrades': same_grades,
            'searchSavingsAgainstFeedback': savings, 'feedbackGatePassed': feedback_gate,
            'otherComparatorsGatePassed': result['qualifiedOnBothMeasures'],
            'fullDevelopmentGatePassed': feedback_gate and result['qualifiedOnBothMeasures']}


def fixture(tasks):
    respond = responder(tasks)
    no_gain = {task: {row['input']: row['expected'] for row in tasks[task]['validation'][:parent.VALIDATION]}
               for task in ('warehouse', 'outage')}

    def reply(request):
        if request['role'] == 'evaluation' and request['instruction'] == parent.grounded.BASELINE:
            passed = no_gain.get(request['task'], {}).get(request['input'])
            if passed is not None:
                return json.dumps(passed, sort_keys=True)
        return respond(request)

    return reply


def run_fixture(seal, directory):
    tasks, plan = prepare()
    with run_with_plan(tasks, plan):
        result = parent.run(seal, directory, fixture(tasks), delivery='fixture')
    verdict = audit(result)
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
    verdict = audit(result)
    parent.staged.save(fresh / 'feedback-gate.json', verdict)
    if (fresh / 'feedback-gate.json').read_bytes() != expected:
        raise ValueError('The feedback gate differs from its exact replay')
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
