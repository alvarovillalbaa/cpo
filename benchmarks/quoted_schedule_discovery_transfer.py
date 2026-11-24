"""Fit the quoted validation schedule on task-disjoint discovery data."""

import argparse
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import reinvested_halving_language_transfer as parent
from cpo._contract import digest
from cpo.quoted_shared_validation_cycle import _screen as quoted_screen


adaptive, joint, controls, native, transfer = parent.adaptive, parent.joint, parent.controls, parent.native, parent.transfer
COHORTS, ROUTED = adaptive.COHORTS, parent.ROUTED
QUOTED = {'quoted-prefix': adaptive.ADAPTIVE, 'quoted-fixed': adaptive.FIXED}
EAGER = {'eager-prefix': adaptive.ADAPTIVE, 'eager-fixed': adaptive.FIXED}
MATCHED = {'quoted-prefix': 'eager-with-quoted-prefix-actions', 'quoted-fixed': 'eager-with-quoted-fixed-actions'}


def limited_quote(incumbent, candidates, rows, evaluate, cap, *, mode, width, limit):
    return quoted_screen(incumbent, candidates[:width], rows, evaluate, min(cap, limit), halve=mode == controls.HALVING)


def screens_with_quotes(plan):
    quoted = {name: partial(limited_quote, mode=mode, width=width, limit=cap)
              for name, mode, width, cap in plan['controls']}
    return {**adaptive.screens(plan), **quoted}


def discovery_contract():
    archived = json.loads(transfer.read_locked(joint.DISCOVERY, joint.DISCOVERY_SHA))
    base = archived['plan']
    if digest(base) != archived['planSha256']:
        raise ValueError('The archived discovery enrollment must match its original seal')
    enrolled = [tuple(item) for group in base['fitEnrollment'].values() for item in group]
    if len(enrolled) != len(set(enrolled)) or {name for name, _ in enrolled} & set(base['targetSubjectsExcluded']):
        raise ValueError('Each discovery panel must occur once and exclude every transfer task')
    root = transfer.ROOT
    files = (Path(__file__).resolve(), Path(adaptive.__file__), Path(controls.__file__), Path(parent.__file__),
             root / 'cpo/quoted_shared_validation_cycle.py', root / 'cpo/certified_shared_validation_cycle.py',
             root / 'cpo/reinvested_shared_validation_cycle.py')
    sources = {str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest() for file in files}
    plan = {**base, 'protocol': 'quoted-schedule-discovery-fit-v1',
            'eagerFitSha256': joint.DISCOVERY_SHA, 'sourceSha256': {**base['sourceSha256'], **sources},
            'scope': 'Preserve the task-disjoint enrollment, every discovery layout and the existing routed '
                     'budget per discovery cohort. Replace the eager uniform and halving actions with '
                     'decision-equivalent quoted actions. Reuse the existing action fit, including a fixed '
                     'schedule and a schedule conditioned on the first already-paid incumbent qualification '
                     'reply. Freeze both selected settings before target scoring.'}
    return plan, archived


def training(plan):
    discovery, groups, *_ = native.prepare()
    geometry, models, static = adaptive.promotion.training_plan()
    if digest(discovery) != plan['discoveryPlanSha256'] or any(
            digest(geometry[key]) != digest(plan[key])
            for key in ('caseCounts', 'challengers', 'seeds', 'fullRosterCap', 'gepaVersion', 'cycles')):
        raise ValueError('The current discovery archive and cycle geometry must reproduce')
    for group, enrollment in plan['fitEnrollment'].items():
        available = {(subject, model) for subject, model, _ in groups[group]}
        if not set(map(tuple, enrollment)) <= available:
            raise ValueError(f'The archived discovery enrollment must reproduce for {group}')
    return groups, models, static


def fit(plan, groups, models, static, archived):
    available = screens_with_quotes(plan)
    if sorted(available) != sorted(plan['actions']):
        raise ValueError('Changing price must preserve the discovery action menu')
    with patch.object(adaptive, 'screens', return_value=available):
        fitted = adaptive.fit(plan, groups, models, static)
    if fitted['baseline'] != archived['baseline']:
        raise ValueError('Every discovery router score and budget must reproduce')
    for policy in QUOTED.values():
        previous, current = archived['fitted'][policy], fitted['fitted'][policy]
        if sum(point['holdoutPasses'] for point in current['byCohort'].values()) < sum(
                point['holdoutPasses'] for point in previous['byCohort'].values()):
            raise ValueError('Quoting cannot remove any previously feasible discovery setting')
    return fitted


def prepare_target(cohort, plan, fitted, archived):
    seal = digest(plan)
    if fitted['planSha256'] != seal or digest(fitted['plan']) != seal:
        raise ValueError('Target replay requires a fit under the current sealed discovery protocol')
    fit_bytes = transfer.read_locked(parent.backup.FIT, parent.backup.FIT_SHA)
    base, panels, models, static, _, gepa, simple = joint.prepare(cohort, fit_bytes)
    subjects = sorted({subject for subject, _, _ in panels})
    enrolled = {subject for group in plan['fitEnrollment'].values() for subject, _ in group}
    if enrolled & set(subjects):
        raise ValueError('No target subject may enter discovery')
    target = {**base, 'protocol': 'quoted-schedule-discovery-transfer-v1', 'trainingPlanSha256': seal,
              'fittedReceiptSha256': digest(fitted), 'eagerFitSha256': joint.DISCOVERY_SHA,
              'sourceSha256': {**base['sourceSha256'], **plan['sourceSha256']}, 'controls': plan['controls'],
              'subjects': subjects,
              'scope': 'Run fixed and first-paid-reply schedules chosen on separate tasks. Replay the '
                       'previous eager fits, the original router, and the new selections with eager costs. '
                       'Reprice common and task-tuned simple controls and native GEPA bounds at the '
                       'quoted setting’s actual spend. Report quality and cost by target cohort.'}
    return target, panels, models, static, gepa, simple, fitted['fitted'], archived['fitted']


def replay(plan, panels, models, static, gepa, simple, quoted_fit, eager_fit):
    quoted, eager = screens_with_quotes(plan), adaptive.screens(plan)
    runners = {ROUTED: adaptive.routed_runner(plan, models, static)}
    for name, policy in QUOTED.items():
        chosen = quoted_fit[policy]['actions']
        runners[name] = partial(adaptive.cycle, actions=tuple(quoted[action] for action in chosen))
        runners[MATCHED[name]] = partial(adaptive.cycle, actions=tuple(eager[action] for action in chosen))
    for name, policy in EAGER.items():
        runners[name] = partial(adaptive.cycle, actions=tuple(eager[action] for action in eager_fit[policy]['actions']))

    vectors = {}
    schedules = {name: dict.fromkeys(plan['subjects'], name) for name in runners}
    totals, hashes = adaptive.replay(plan, panels, runners, schedules, vectors)
    if totals[ROUTED] != simple['cpo'][ROUTED] or any(
            hashes[panel][ROUTED] != point[ROUTED] for panel, point in simple['cpoTrajectoryHashes'].items()):
        raise ValueError('The original router must reproduce its score, spend and paid paths')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for name, matched in MATCHED.items():
        if (any(scores[name] != scores[matched] for scores in vectors.values())
                or totals[name]['paidLookups'] > totals[matched]['paidLookups']):
            raise ValueError('Using quoted execution must preserve held-out decisions at no higher cost')
        budget = totals[name]['paidLookups']
        scores = {subject: dict(rows) for subject, rows in vectors.items()}
        simple_matched = parent.compare_simple(plan, panels, simple, budget, scores)
        bounds, attainers = parent.compare_native(plan, panels, gepa, budget,
                                                   simple['settingsTotals'][parent.RETAIN]['holdoutPasses'], scores)
        effects = {other: paired(scores, name, other, plan)
                   for other in (ROUTED, *EAGER, matched, *simple_matched, *attainers)}
        upper = bounds['subject-tuned-gepa']['upperPasses']
        score = totals[name]['holdoutPasses']
        comparisons[name] = {'simpleAtBudget': simple_matched, 'nativeBoundsAtBudget': bounds,
                             'replayedNativeAnchors': attainers, 'paired': effects,
                             'beatsNativeUpperBound': upper is not None and score > upper,
                             'beatsTaskTunedSimple': score > simple_matched['subject-tuned-simple']['holdoutPasses'],
                             'routerBudgetMet': budget <= totals[ROUTED]['paidLookups']}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'comparisons': comparisons,
            'trajectoryHashes': hashes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, archived = discovery_contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fitted receipt')
        plan, *inputs = prepare_target(args.cohort, plan, json.loads(args.fitted.read_bytes()), archived)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    report = fit(plan, *training(plan), archived) if args.fit else {
        'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs),
    }
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
