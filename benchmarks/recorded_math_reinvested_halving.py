"""Audit whether exact shortlist savings improve low-budget CPO search."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_math_budget_crossfit as parent
from cpo._contract import digest
from cpo.reinvested_shared_validation_cycle import _screen, run_reinvested_shared_validation_cycle
from cpo.two_sided_certificate_cycle import _run


CROSSFIT_SHA = {
    'root/4': '0ce70d2617e1848c0045b711751dececc862c70ed4f75b50fcf8058bc6c09188',
    'root/8': '5fda410a9c8bed084154b296a942703b7e28cb3e28e297b4e0ad425541617382',
    'rotated/4': '978b4b349997a8f5f0276bbae196f5e150bb1cd83028566077348ca12c4dc903',
    'rotated/8': '107d4e51bfc7f222fbf6a3445e97a5eef8e56feff7f704c9323f34bf40b18935',
}
ARM = 'reinvested-halving'
METRICS = parent.previous.METRICS


def prepare(group, width):
    base, data, models, static, priors = parent.prepare(group, width)
    root = parent.math.ROOT
    lock = CROSSFIT_SHA[f'{group}/{width}']
    path = f'docs/recorded-math-budget-crossfit-{group}-{width}-v1.json'
    receipt = json.loads(parent.frontier.transfer.read_locked(path, lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('The low ceilings must use the published calibration and audit folds')
    files = (Path(__file__).resolve(), root / 'cpo/reinvested_shared_validation_cycle.py',
             root / 'cpo/certified_shared_validation_cycle.py', root / 'benchmarks/continuous_search_controls.py')
    sources = {str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest() for path in files}
    plan = {**base, 'protocol': 'recorded-math-reinvested-halving-v1', 'crossfitSha256': lock,
            'crossfitPlanSha256': digest(base), 'sourceSha256': {**base['sourceSha256'], **sources},
            'scope': 'Evaluate a funded halving round on a common validation row, skipping only grades '
                     'that cannot change the exact shortlist. Spend saved lookups on further full rounds. '
                     'Keep the same halving rungs and independent qualification as the simple control. '
                     'At the prior low ceiling, sweep every funded integer cap with four and, where '
                     'available, eight challengers. Select a new setting on each calibration fold, check '
                     'eager parity with reuse disabled, and replay only the selected setting on the audit fold. '
                     'The expanded CPO menu replaces the old setting only if calibration improves its '
                     'pass total or its paid cost at equal passes.'}
    return plan, data, models, static, priors, receipt['results']


def settings(task, width):
    return tuple(f'{ARM}/{size}/{cap}' for size in (4, 8) if size <= width
                 for cap in range(max(size + 1, task['validation']), task['searchCaps']['low'] + 1))


def grade(cells, trials, labels, priors, *, check_eager=False):
    points = {name: Counter() for name in labels}
    without_reuse = {name: Counter() for name in labels}
    size = len(next(iter(cells.values())))
    vectors = {name: {'selected': [0] * size, 'withoutReuse': [0] * size} for name in labels}
    binary = {prompt: tuple(cell[0] for cell in row) for prompt, row in cells.items()}
    proof = partial(parent.finish_joint_order, priors=priors)
    run = parent.native.paired.cycle.execute_path
    parity = partial(_run, screen=partial(_screen, reinvest=False))
    with patch.object(parent.joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', proof):
        for base, roster, roles, seed in trials:
            for name in labels:
                _, width, cap = name.split('/')
                roster_width, allowance = int(width), int(cap)
                args = binary, base, roster[:roster_width], roles, seed, allowance, 1
                result, ledger = run(run_reinvested_shared_validation_cycle, *args)
                control, control_ledger = run(parity, *args)
                if check_eager:
                    screen = partial(parent.simple.screen, mode=parent.simple.HALVING, width=roster_width)
                    eager, eager_ledger = run(partial(_run, screen=screen), *args)
                    if (eager.search.finalist != control.search.finalist or eager.qualification != control.qualification
                            or not control_ledger.keys() <= eager_ledger.keys()):
                        raise ValueError('Certified halving without reuse must preserve the funded eager trajectory')
                rounds_by_arm = {}
                for kind, path, paid, totals in (('selected', result, ledger, points),
                                                 ('withoutReuse', control, control_ledger, without_reuse)):
                    parent.joint.continuous.routing.verify_qualification(binary, base, roles, path, paid, 1)
                    grades = [binary[path.prompt][case] for case in roles[-1]]
                    rounds = sum(role == 'validation' and prompt == base for role, prompt, _ in paid)
                    rounds_by_arm[kind] = rounds
                    totals[name].update(holdoutPasses=sum(grades), paidLookups=len(paid), validationRounds=rounds)
                    parent.previous.accumulate(vectors[name][kind], roles[-1], grades)
                extra = rounds_by_arm['selected'] - rounds_by_arm['withoutReuse']
                if extra < 0:
                    raise ValueError('Reinvestment cannot fund fewer validation rounds')
                points[name].update(changedNominees=int(result.search.finalist != control.search.finalist),
                                    extraRounds=extra)
    return points, without_reuse, vectors


def calibration_rank(point):
    return -point['holdoutPasses'], point['paidLookups']


def measure(plan, subject, cells, models, static, priors, reference):
    task = plan['datasets'][subject]
    width, group = plan['rosterWidth'], plan['group']
    available = settings(task, width)
    reports, audits = [], {}
    effect = parent.native.frozen.paired_effects.paired_effect
    for previous in reference['directions']:
        first, second = previous['calibrationFold'], previous['auditFold']
        before = previous['comparisons']['low']
        calibration, trials, _ = parent.get_fold(cells, task, first, group, width)
        points, without_reuse, _ = grade(calibration, trials, available, priors, check_eager=True)
        best = min(available, key=lambda name: (*calibration_rank(points[name]), name))
        use_new = calibration_rank(points[best]) < calibration_rank(before['calibration']['cpo'])
        audit, trials, _ = parent.get_fold(cells, task, second, group, width)
        observed, control, scores = grade(audit, trials, (best,), priors, check_eager=True)
        labels = sorted({point['setting'] for point in before['audit'].values()})
        checked, vectors = parent.score_settings(audit, trials, labels, models, static, priors)
        for point in before['audit'].values():
            if checked[point['setting']] != {key: point[key] for key in METRICS}:
                raise ValueError('The frozen low-ceiling GEPA, simple and CPO points must reproduce')
        base = {name: point for name, point in before['audit'].items()}
        new = {'setting': best, **observed[best]}
        folds = {name: vectors[point['setting']] for name, point in base.items()}
        folds.update(reinvested=scores[best]['selected'], withoutReuse=scores[best]['withoutReuse'])
        folds['expanded'] = folds['reinvested' if use_new else 'cpo']
        audits[f'fold-{second}'] = folds
        reports.append({'calibrationFold': first, 'auditFold': second, 'episodes': len(trials),
                        'calibrationSettings': points, 'calibrationWithoutReuse': without_reuse,
                        'calibrationChoice': {'setting': best, **points[best]}, 'expandedChoseNew': use_new,
                        'audit': {**base, 'reinvested': new, 'withoutReuse': {'setting': best, **control[best]},
                                  'expanded': new if use_new else base['cpo']}})
    comparisons = {candidate: {name: effect(audits, candidate, name, plan) for name in ('cpo', 'gepa', 'simple')}
                   for candidate in ('expanded', 'reinvested')}
    comparisons['reinvested']['withoutReuse'] = effect(audits, 'reinvested', 'withoutReuse', plan)
    return {'directions': reports, 'pairedAudit': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('root', 'rotated'), required=True)
    parser.add_argument('--width', type=int, choices=(4, 8), required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, models, static, priors, reference = prepare(args.group, args.width)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    results = {subject: measure(plan, subject, parent.math.load_cells(subject, data[subject]['record']),
                               models, static, priors, reference[subject]) for subject in plan['datasets']}
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
