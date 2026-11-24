"""Select lookup-capped methods on one archive fold and audit them on the other."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_math_router_frontier as frontier
from cpo._contract import digest
from cpo.joint_order_qualification import finish_joint_order
from cpo.paired_order_certificate_cycle import run_paired_order_certificate_cycle
from cpo.two_sided_certificate_cycle import _run


previous, native, joint = frontier.previous, frontier.native, frontier.joint
math, simple = previous.prior.math, previous.simple
ROUTED, STRICT, RETAIN = frontier.ROUTED, frontier.STRICT, frontier.RETAIN
MENUS = ('cpo', 'gepa', 'simple')
FRONTIER_SHA = {
    'root/4': '94771a45cbfa7cec0e086ab6ae5121d0596a3efc6e4856e460697ae4ba357915',
    'root/8': 'af181a0ddd72d25a37b0ea4c22521a99817b92a8d8ed84c90a64a901cb8883ca',
    'rotated/4': '01d1b0415bb7eab21600f78fdffc9cc057ab8c3760f0d39821b31ce2c6387e61',
    'rotated/8': '7f1a06a284b4f6637ebdbed0ca4c9c827a5611c2c114a9b27bd13b88a8f7a607',
}


def partition(subject, identities):
    if len(set(identities)) != len(identities):
        raise ValueError('Archive cases must have unique identities')
    ordered = sorted(range(len(identities)), key=lambda i: digest(['math-budget-crossfit-v1', subject, identities[i]]))
    half = len(ordered) // 2
    return tuple(sorted(ordered[:half])), tuple(sorted(ordered[half:]))


def prepare(group, width):
    parent, data, models, static, fit, _ = frontier.prepare(group, width)
    lock = FRONTIER_SHA[f'{group}/{width}']
    path = f'docs/recorded-math-router-frontier-{group}-{width}-v1.json'
    receipt = json.loads(frontier.transfer.read_locked(path, lock))
    if receipt['planSha256'] != digest(parent):
        raise ValueError('The case split must use the original candidate pools, tiers and method sources')
    tasks = {}
    for subject, layout in parent['datasets'].items():
        record = data[subject]['record']
        ids = record['cases'] if subject == 'arc' else list(range(record['caseCount']))
        train, validation, qualification, _ = layout['cohorts']
        folds = partition(subject, ids)
        full_cap = validation * (1 + width)
        caps = dict(zip(('low', 'middle', 'high'), (19, (19 + full_cap) // 2, full_cap), strict=True))
        tasks[subject] = {'seeds': layout['seeds'], 'folds': folds, 'training': train // 2,
                          'validation': validation, 'qualification': qualification, 'searchCaps': caps}
    source = Path(__file__).resolve()
    plan = {**parent, 'protocol': 'recorded-math-budget-crossfit-v1', 'parentFrontierSha256': lock,
            'parentPlanSha256': digest(parent), 'datasets': tasks,
            'sourceSha256': {**parent['sourceSha256'], str(source.relative_to(math.ROOT)): sha256(source.read_bytes()).hexdigest()},
            'scope': 'Split archived cases into two disjoint folds by hashed identity before applying any episode splits. '
                     'Each direction tunes on its calibration fold only. Audit only the selected settings on the other '
                     'fold. Keep validation and qualification widths, halve training, and hold out the remaining cases. '
                     'Apply one shared hard cap per episode, with up to two reads per qualification case reserved in '
                     'addition to the search allowance. Report realized lookups and case-paired effects in both directions.'}
    priors = previous.allocation.witness.previous.priors_of(fit)
    return plan, data, models, static, priors


def get_fold(cells, task, index, group, width):
    cases = task['folds'][index]
    subset = {prompt: tuple(vector[case] for case in cases) for prompt, vector in cells.items()}
    training, validation, qualification = (task[key] for key in ('training', 'validation', 'qualification'))
    held = len(cases) - training - validation - qualification
    if held <= 0:
        raise ValueError('Every archive fold needs a held-out panel')
    layout = {'seeds': task['seeds'], 'cohorts': (training, validation, qualification, held)}
    trials = list(previous.prior.trials(subset, layout, group, width))
    return subset, trials, held


def search_cap(setting):
    if setting == RETAIN:
        return 0
    return int(setting.split('/')[1 if ':' in setting else -1])


def pick(totals, labels, cap, qualification, episodes):
    funded = [label for label in labels if search_cap(label) <= cap]
    return native.gepa.best_fixed(totals, funded, episodes * (cap + 2 * qualification))


def calibrate(plan, task, cells, trials, models, static, priors):
    totals, _, cpo, simple_labels = frontier.sweep_cpo(plan, cells, trials, models, static, priors)
    native_totals = previous.native_settings(cells, trials, {**plan, 'searchCap': max(task['searchCaps'].values())})
    menus = {'cpo': (totals, cpo), 'gepa': (native_totals, tuple(native_totals)), 'simple': (totals, simple_labels)}
    selection = {tier: {method: pick(points, labels, cap, task['qualification'], len(trials))
                        for method, (points, labels) in menus.items()}
                 for tier, cap in task['searchCaps'].items()}
    return selection, {method: digest(points) for method, (points, _) in menus.items()}


def score_settings(cells, trials, settings, models, static, priors):
    routed = joint.adaptive.promotion.runner_map(models, static)
    engines = {ROUTED: routed[joint.ROUTED], frontier.STATIC: routed[joint.adaptive.continuous.STATIC],
               frontier.DEFERRED: run_paired_order_certificate_cycle}
    controls = {name: partial(_run, screen=partial(simple.screen, mode=mode, width=width))
                for name, mode, width, _ in simple.settings(len(trials[0][2][1]))}
    proof = partial(finish_joint_order, priors=priors)
    size = len(next(iter(cells.values())))
    points = {name: Counter() for name in settings}
    vectors = {name: [0] * size for name in settings}
    binary = {prompt: tuple(cell[0] for cell in row) for prompt, row in cells.items()}

    def score(name, start, roster, roles, seed):
        cap = search_cap(name)
        family = name.split('/')[0]
        held = roles[-1]
        if name == RETAIN:
            return 0, [binary[start][case] for case in held]
        if family == STRICT:
            point, _, grades = math.run_trial(cells, start, roster, roles, seed, 'strict', cap)
            return point['paidLookups'], grades
        if ':' in name:
            group, mode = family.split(':')
            width = len(roles[1]) // (2 if group == 'half' else 1)
            args = native.validation_width((cells, start, roster, roles, seed), width)
            rule = name.rsplit('/', 1)[1]
            point, _, grades = native.gepa.native_paths(args, mode, cap, cap)[rule][cap]
            return point['paidLookups'], grades
        run = native.paired.cycle.execute_path
        args = binary, start, roster, roles, seed, cap, 1
        if name in controls:
            with patch.object(joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', proof):
                result, ledger = run(controls[name], *args)
        else:
            result, ledger = run(engines[family], *args)
        joint.continuous.routing.verify_qualification(binary, start, roles, result, ledger, 1)
        return len(ledger), [binary[result.prompt][case] for case in held]

    with native.split_safe_cache():
        for start, roster, roles, seed in trials:
            for name in settings:
                paid, grades = score(name, start, roster, roles, seed)
                if paid > search_cap(name) + 2 * len(roles[2]):
                    raise ValueError('A path exceeded its search allowance plus two qualification cells per case')
                points[name].update(holdoutPasses=sum(grades), paidLookups=paid)
                previous.accumulate(vectors[name], roles[-1], grades)
    return points, vectors


def measure_subject(plan, subject, cells, models, static, priors):
    task = plan['datasets'][subject]
    group, width = plan['group'], plan['rosterWidth']
    reports = []
    audits_by_tier = {tier: {} for tier in task['searchCaps']}
    effect = native.frozen.paired_effects.paired_effect
    for index in (0, 1):
        calibration, trials, held = get_fold(cells, task, index, group, width)
        selected, hashes = calibrate(plan, task, calibration, trials, models, static, priors)
        settings = sorted({point['setting'] for menus in selected.values() for point in menus.values()})
        checked, _ = score_settings(calibration, trials, settings, models, static, priors)
        if any(checked[point['setting']] != {key: point[key] for key in previous.METRICS}
               for menus in selected.values() for point in menus.values()):
            raise ValueError('Selected settings must reproduce their calibration score and spend')
        other = 1 - index
        audit, audit_trials, audit_held = get_fold(cells, task, other, group, width)
        points, vectors = score_settings(audit, audit_trials, settings, models, static, priors)
        summary = {}
        for tier, winners in selected.items():
            local = {method: vectors[point['setting']] for method, point in winners.items()}
            audits_by_tier[tier][f'fold-{other}'] = local
            summary[tier] = {'calibration': winners,
                             'audit': {method: {'setting': point['setting'], **points[point['setting']]}
                                       for method, point in winners.items()},
                             'pairedAudit': {control: effect({subject: local}, 'cpo', control, plan)
                                             for control in MENUS[1:]}}
        reports.append({'calibrationFold': index, 'auditFold': other, 'episodes': len(trials),
                        'calibrationHoldoutRowsPerEpisode': held, 'auditHoldoutRowsPerEpisode': audit_held,
                        'calibrationTotalsSha256': hashes, 'comparisons': summary})
    return {'directions': reports,
            'pairedAcrossAuditFolds': {tier: {control: effect(folds, 'cpo', control, plan) for control in MENUS[1:]}
                                       for tier, folds in audits_by_tier.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('root', 'rotated'), required=True)
    parser.add_argument('--width', type=int, choices=(4, 8), required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data, models, static, priors = prepare(args.group, args.width)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    results = {subject: measure_subject(plan, subject, math.load_cells(subject, data[subject]['record']),
                                        models, static, priors) for subject in plan['datasets']}
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
