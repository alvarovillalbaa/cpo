"""Validate task-specific schedule changes before an independent model audit."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import quoted_schedule_checkpoint_transfer as parent
from cpo._contract import digest
from cpo.two_sided_certificate_cycle import _run


native, transfer, adaptive = parent.native, parent.transfer, parent.adaptive
QUOTED, EAGER, GEPA, RETAIN, ROUTED, PREFIX = (
    parent.QUOTED, parent.EAGER, parent.GEPA, parent.RETAIN, parent.ROUTED, parent.PREFIX,
)
GUARDED, UNGUARDED = 'guarded-quote', 'smaller-calibration-quote'
RECEIPTS = dict(zip(parent.discovery.COHORTS, (
    'b85b2730887a10f0c9ae3c6a3078b85c947565a4a6957aaa9ddca8a1e499be4a',
    'c3d7814b8973da05502cc3ca0df2c9fba0f6a40a353f0419215e998a6f492b8a',
    'eb48fed8622c6a068b06c34280f7154df7d81fe3b01712b3ab447af841c059fc',
    '54bf310b90b03bc5c389ce36f869dce64188ffdeac9276ffabcb8b3f12982639',
    'ca79215e523ad2ce57e098722719988a33bf2e9743f2bbb66b79ffa4eba81775',
    'f54c53965a21c5e3c5195782c58f235360492f3678c3c41db835eebf84f5e28b',
    '69ab23b5d23caa7db70923c59afa0fd4d050704e1a57c9acc69ab8df57dca5da',
), strict=True))


def prepare(cohort):
    base, tasks, models, static, frozen = parent.prepare(cohort)
    lock = RECEIPTS[cohort]
    name = f'docs/quoted-schedule-checkpoint-transfer-{cohort.lower()}-v1.json'
    receipt = json.loads(transfer.read_locked(name, lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('The model pairs and original audit benchmark must reproduce')
    folds = {subject: [parent.split_cases(f'{subject}/guard', held) for held in pair['folds']]
             for subject, pair in base['pairs'].items()}
    source = Path(__file__).resolve()
    plan = {**base, 'protocol': 'quoted-schedule-guarded-transfer-v1', 'checkpointReceiptSha256': lock,
            'sourceSha256': {**base['sourceSha256'], str(source.relative_to(transfer.ROOT)):
                             sha256(source.read_bytes()).hexdigest()},
            'selectionAndGuardCases': folds,
            'scope': 'Keep each original model, seed and audit split. Divide the calibration scoring cases '
                     'into selection and guard cases by hashed identity. Select a task-specific quoted '
                     'schedule at the calibration router price using only selection grades. On guard cases '
                     'of the same model, switch from the frozen discovery prefix only at no higher price '
                     'and a nonnegative lower paired endpoint, with a strict saving or positive endpoint. '
                     'Keep the target model and all audit scoring cases outside the guard. Reproduce the '
                     'original audit controls and compare the smaller-selection policy with and without the guard.'}
    return plan, tasks, models, static, frozen, receipt['results']


def accept(lower, task_paid, prefix_paid):
    return lower >= 0 and task_paid <= prefix_paid and (lower > 0 or task_paid < prefix_paid)


def score(plan, subject, matrix, held, seeds, runners):
    cells, _ = transfer.case_cells(matrix)
    totals = {name: Counter() for name in runners}
    vectors = {name: [0] * len(held) for name in runners}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for start, stages in parent.layouts(plan, subject, matrix, seeds, held):
        for name, runner in runners.items():
            paid, grades = parent.rollout(cells, start, stages, runner, plan['nativeSearchCap'])
            totals[name].update(holdoutPasses=sum(grades), paidLookups=paid)
            add(vectors[name], grades)
    return totals, vectors


def measure(plan, tasks, models, static, frozen, reference):
    router = adaptive.routed_runner(plan, models, static)
    quoted, eager = parent.discovery.screens_with_quotes(plan), adaptive.screens(plan)
    prefix = partial(adaptive.cycle, actions=tuple(quoted[action] for action in frozen))
    engines = {label: {name: partial(_run, screen=screens[name]) for name, *_ in plan['controls']}
               for label, screens in ((QUOTED, quoted), (EAGER, eager))}
    options = {**engines[QUOTED], RETAIN: None}
    paired = native.frozen.paired_effects.paired_effect
    totals, outcomes, vectors = {}, {}, {}
    changes = Counter()
    for subject, original in reference['directions'].items():
        outcomes[subject] = []
        for row in original:
            first, second = row['calibrationFold'], row['auditFold']
            selection, guard = plan['selectionAndGuardCases'][subject][first]
            audit_cases = plan['pairs'][subject]['folds'][second]
            training = tasks[subject][row['calibrationModel']]
            target = tasks[subject][row['auditModel']]
            seeds = plan['calibrationSeeds']
            fitted, _ = score(plan, subject, training, selection, seeds, {**options, ROUTED: router})
            budget = fitted.pop(ROUTED)['paidLookups']
            if budget != row['calibrationRouter']['paidLookups']:
                raise ValueError('Holding out scoring cases must preserve the original calibration price')
            selected = native.gepa.best_fixed(fitted, tuple(name for name in options if name != RETAIN), budget)
            runner = options[selected['setting']]
            guard_costs, guard_vectors = score(plan, subject, training, guard, seeds,
                                               {UNGUARDED: runner, PREFIX: prefix})
            effect = paired({subject: guard_vectors}, UNGUARDED, PREFIX, plan)
            switched = accept(effect['pairedRange95'][0], guard_costs[UNGUARDED]['paidLookups'],
                              guard_costs[PREFIX]['paidLookups'])
            old, audited = parent.audit(plan, subject, target, audit_cases, engines, router, prefix,
                                        row['calibrationSetting'])
            if old != row['audit']:
                raise ValueError('Every original audit point must reproduce before evaluating the guard')
            fresh, fresh_scores = score(plan, subject, target, audit_cases, plan['auditSeeds'], {UNGUARDED: runner})
            points = {**old, **fresh}
            audited.update(fresh_scores)
            choice = UNGUARDED if switched else PREFIX
            points[GUARDED] = points[choice]
            audited[GUARDED] = audited[choice]
            for name, point in points.items():
                totals.setdefault(name, Counter()).update(point)
            vectors[f'{subject}/{second}'] = audited
            changes.update(switched=int(switched),
                           selectedDifferently=int(selected['setting'] != row['calibrationSetting'][QUOTED]['setting']))
            outcomes[subject].append({'calibrationModel': row['calibrationModel'], 'auditModel': row['auditModel'],
                                      'selectionFold': first, 'auditFold': second, 'selected': selected,
                                      'calibrationBudget': budget, 'guardCosts': guard_costs, 'guardEffect': effect,
                                      'switched': switched, 'audit': points})
    if totals[PREFIX] != reference['auditTotals'][PREFIX]:
        raise ValueError('The frozen prefix aggregate must match the original audit receipt')
    effects = {name: paired(vectors, GUARDED, name, plan) for name in totals if name != GUARDED}
    return {'auditEpisodes': reference['auditEpisodes'], 'directions': outcomes, 'switchCounts': changes,
            'auditTotals': totals, 'pairedGuarded': effects}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=parent.discovery.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
