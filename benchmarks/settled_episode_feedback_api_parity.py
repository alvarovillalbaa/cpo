"""Match the opt-in feedback API against the sealed qualification replay."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_qualification_feedback as feedback
from benchmarks import settled_episode_refit as refit
from cpo import Observation, Row
from cpo._contract import digest
from cpo.feedback_episode import run_feedback_episode
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.settled_episode import EpisodeCycle
from cpo.single_finalist import FinalistResult


FEEDBACK_SHA = '0f62d18925adaa00c4e34f6678fc2fabcb0015c20f235ec0067562435b984268'


def compare(plan, panels, models, static, rules):
    runners = feedback.override.runners(plan, models, static)
    cap = max(limit for _, _, _, limit in plan['controls'])
    run = refit.native.paired.cycle.execute_path
    totals, schedules, trace = Counter(), Counter(), sha256()
    episodes = 0
    for subject, model, seed, cells, stages, start in refit.previous.episodes(plan, panels):
        state, paid_probe = refit.previous.probe(refit.EAGER, plan['probeModes'], cells, stages, start)
        base, trigger, follow_up = rules[int(state)]
        probe_count = refit.probe_cost(rules, int(not paid_probe[0][2]), int(paid_probe[0][2]), settled=True)
        expected_paid = [('training', prompt, str(case), grade) for prompt, case, grade in paid_probe[:probe_count]]
        incumbent, outcome = start, None
        expected_cycles, expected_schedules = [], []
        for local_seed, roster, roles in stages:
            schedule = follow_up if outcome == trigger else base
            if schedule == refit.RETAIN:
                decision = FixedPoolCycleResult(FinalistResult(incumbent, None, 0), None)
                outcome = 'skipped'
            else:
                decision, ledger = run(runners[schedule], cells, incumbent, roster, roles, local_seed, cap, 1)
                expected_paid.extend((*key, grade) for key, grade in ledger.items())
                outcome = feedback.outcome(decision)
            incumbent = decision.prompt
            expected_cycles.append(decision)
            expected_schedules.append(schedule)

        actual_paid = []

        def grade(prompt, row):
            passed = bool(cells[prompt][int(row.id)])
            actual_paid.append((row.family, prompt, row.id, passed))
            return passed

        def qualify(prompt, row, repeat):
            if repeat != 0:
                raise ValueError('The archive funds one qualification reply per prompt and case')
            return grade(prompt, row)

        training = tuple(Row(str(case), 'training') for case in stages[0][2][0][:2])
        cycles = tuple(
            EpisodeCycle(tuple(roster), tuple(Row(str(case), 'validation') for case in roles[1]),
                         tuple(Row(str(case), 'qualification') for case in roles[2]), local_seed)
            for local_seed, roster, roles in stages
        )
        result = run_feedback_episode(
            start, training, cycles, lambda prompt, row: Observation(grade(prompt, row), {}),
            probe=grade, qualify=qualify,
        )
        if (result.prompt != incumbent or result.schedule != base or result.cycles != tuple(expected_cycles)
                or result.cycle_schedules != tuple(expected_schedules) or result.training_evaluations != probe_count
                or result.evaluations != len(actual_paid) or actual_paid != expected_paid):
            raise ValueError(f'Feedback API diverged on {subject}/{model}/{seed}')
        episodes += 1
        schedules.update(result.cycle_schedules)
        totals.update(holdoutPasses=sum(cells[result.prompt][case] for case in stages[0][2][-1]),
                      paidLookups=result.evaluations, trainingLookups=result.training_evaluations,
                      overriddenCycles=sum(action != result.schedule for action in result.cycle_schedules))
        trace.update(bytes.fromhex(digest((subject, model, seed, result.prompt, result.cycle_schedules, actual_paid))))
    return {'episodes': episodes, 'totals': totals, 'cycleSchedules': schedules, 'paidTraceSha256': trace.hexdigest()}


def verify():
    transfer = refit.transfer
    plan, context, baseline = refit.contract()
    if version('gepa') != plan['gepaVersion'] or plan['cycles'] != 3:
        raise ValueError('Use pinned GEPA and the three-cycle archive')
    frozen = json.loads(transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    receipt = json.loads(transfer.read_locked('docs/settled-episode-qualification-feedback-v1.json', FEEDBACK_SHA))
    if receipt['fitReceiptSha256'] != parity.FIT_SHA or receipt['transferReceiptSha256'] != parity.LOCKS:
        raise ValueError('Use the fitted feedback policy and its original target enrollment')
    for source, checksum in receipt['sourceSha256'].items():
        transfer.read_locked(source, checksum)
    fit = receipt['discovery']['policies'][feedback.CONDITIONAL]
    rules = tuple(tuple(entry) for entry in fit['rules'])
    results = {}
    for cohort in refit.discovery.COHORTS:
        target, (panels, models, static, *_) = refit.target(cohort, plan, context, baseline, frozen)
        name = cohort.lower()
        archived = json.loads(transfer.read_locked(
            f'docs/settled-episode-refit-transfer-{name}-v1.json', parity.LOCKS[name],
        ))
        if digest(target) != archived['planSha256'] or digest(archived['plan']) != archived['planSha256']:
            raise ValueError('Use the original target layout')
        point = compare(target, panels, models, static, rules)
        prior = receipt['archivedTransfer'][cohort]
        if point['totals'] != prior['policies'][feedback.CONDITIONAL] or point['episodes'] != prior['episodes']:
            raise ValueError(f'Feedback API must reproduce the sealed target totals on {cohort}')
        results[cohort] = point
    files = (Path(__file__).resolve(), transfer.ROOT / 'cpo/feedback_episode.py', transfer.ROOT / 'cpo/settled_episode.py')
    return {'protocol': 'settled-episode-feedback-api-parity-v1', 'feedbackReceiptSha256': FEEDBACK_SHA, 'rules': rules,
            'sourceSha256': {str(file.relative_to(transfer.ROOT)): sha256(file.read_bytes()).hexdigest()
                             for file in files},
            'providerRequests': 0, 'cohorts': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a fresh receipt path')
    result = verify()
    with args.out.open('x') as output:
        output.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
