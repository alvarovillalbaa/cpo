"""Calibrate a probe-free opening on one math archive fold and audit the other."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import full_roster_precheck_math as transfer
from benchmarks import recorded_math_budget_crossfit as crossfit
from benchmarks.full_roster_no_nominee_repair import PARENT_SHA
from cpo._contract import digest
from cpo.feedback_episode import FeedbackEpisodeResult
from cpo.full_roster_precheck import _cycle
from cpo.settled_episode import _ACTIONS, _MAX_VALIDATION_READS


NATIVE = transfer.math_transfer
ADAPTIVE = transfer.FULL_ROSTER
FIXED = 'calibrated-fixed-opening'
GEPA = 'calibrated-gepa-or-retain'
ARMS = (ADAPTIVE, *_ACTIONS)
METRICS = ('holdoutPasses', 'paidLookups')


def prepare():
    parent, data = transfer.prepare()
    root = transfer.math.ROOT
    archived = (root / 'docs/full-roster-precheck-math-v1.json').read_bytes()
    if sha256(archived).hexdigest() != PARENT_SHA:
        raise ValueError('Use the exact archived math transfer')
    receipt = json.loads(archived)
    if digest(receipt['plan']) != receipt['planSha256'] or digest(parent) != receipt['planSha256']:
        raise ValueError('The math transfer plan must reproduce')

    datasets = {}
    for subject, layout in parent['datasets'].items():
        record = data[subject]['record']
        identities = record['cases'] if subject == 'arc' else range(record['caseCount'])
        training, validation, _, _ = layout['cohorts']
        datasets[subject] = {'seeds': layout['seeds'], 'folds': crossfit.partition(subject, tuple(identities)),
                             'training': training // 2, 'validation': validation,
                             'qualification': parent['qualificationRows']}
    paths = (__file__, crossfit.__file__, NATIVE.native.gepa.__file__)
    sources = {str(Path(path).resolve().relative_to(root)): sha256(Path(path).read_bytes()).hexdigest()
               for path in paths}
    cap = 2 + _MAX_VALIDATION_READS + 2 * parent['qualificationRows']
    return {**parent, 'protocol': 'cpo-full-roster-fixed-opening-v1', 'datasets': datasets,
            'parentPlanSha256': receipt['planSha256'], 'parentReceiptSha256': PARENT_SHA,
            'sourceSha256': {**parent['sourceSha256'], **sources}, 'primaryArms': (ADAPTIVE, FIXED, GEPA),
            'fixedMenu': _ACTIONS, 'searchCap': cap - 2 * parent['qualificationRows'], 'totalCap': cap,
            'scope': ('Fit one fixed opening per subject, geometry and calibration direction. '
                      'Replay the published full-roster route and its three schedules with no training reads. '
                      'Fit both the fixed policy and split-safe GEPA or retention at the adaptive arm\'s realized '
                      'calibration lookup budget, with one shared hard per-trial cap. '
                      'Audit only the selected settings and the published adaptive route on the other fold.')}, data


def run_fixed(schedule, incumbent, _training, cycles, evaluate, *, probe, qualify):
    (cycle,) = cycles
    result = _cycle(schedule, incumbent, cycle, evaluate, qualify)
    return FeedbackEpisodeResult(result.prompt, schedule, 0, (result,), (schedule,))


def cpo_points(plan, cells, trials, settings):
    totals = {label: Counter() for label in settings}
    vectors = {label: [0] * len(next(iter(cells.values()))) for label in settings}
    runners = {ADAPTIVE: transfer.RUNNERS[ADAPTIVE],
               **{label: partial(run_fixed, label) for label in _ACTIONS}}
    for trial in trials:
        for label in settings:
            result, cost, grades, _ = transfer.episode(runners[label], cells, trial)
            if (result.evaluations > plan['totalCap'] or
                    (label != ADAPTIVE and result.training_evaluations != 0)):
                raise ValueError('A replay exceeded its budget or a fixed opening used a training reply')
            totals[label].update(cost)
            NATIVE.accumulate(vectors[label], trial[2][-1], grades)
    return totals, vectors


def gepa_point(plan, cells, trials, setting):
    totals = Counter(paidLookups=0, holdoutPasses=0)
    vector = [0] * len(next(iter(cells.values())))
    with NATIVE.native.split_safe_cache():
        for start, roster, roles, seed in trials:
            if setting == NATIVE.RETAIN:
                grades = [cells[start][case][0] for case in roles[-1]]
                paid = 0
            else:
                group, spec = setting.split(':', 1)
                mode, cap, rule = spec.split('/')
                cap = int(cap)
                width = len(roles[1]) // (2 if group == 'half' else 1)
                args = NATIVE.native.validation_width((cells, start, roster, roles, seed), width)
                point, _, grades = NATIVE.native.gepa.native_paths(args, mode, cap, cap)[rule][cap]
                paid = point['paidLookups']
                if paid > cap + 2 * len(roles[2]):
                    raise ValueError('A native path exceeded search and independent qualification funding')
            if paid > plan['totalCap']:
                raise ValueError('A native path exceeded the shared trial cap')
            totals.update(paidLookups=paid, holdoutPasses=sum(grades))
            NATIVE.accumulate(vector, roles[-1], grades)
    return totals, vector


def measure(plan, subject, cells, group, width):
    effects = NATIVE.native.frozen.paired_effects.paired_effect
    accumulated = {}
    directions = []
    task = plan['datasets'][subject]
    for index in (0, 1):
        calibration, trials, _ = crossfit.get_fold(cells, task, index, group, width)
        totals, _ = cpo_points(plan, calibration, trials, ARMS)
        budget = totals[ADAPTIVE]['paidLookups']
        # The fitted menu may fall back to the published policy if every static
        # schedule exceeds the realized calibration budget.
        fitted = min((label for label in ARMS if totals[label]['paidLookups'] <= budget),
                     key=lambda label: (-totals[label]['holdoutPasses'], totals[label]['paidLookups'], label))
        native = NATIVE.native_settings(calibration, trials, plan)
        control = NATIVE.native.gepa.best_fixed(native, tuple(native), budget)
        verified, _ = gepa_point(plan, calibration, trials, control['setting'])
        if any(verified[key] != control[key] for key in METRICS):
            raise ValueError('The selected GEPA setting must reproduce its calibration point')

        audit, audit_trials, holdout_width = crossfit.get_fold(cells, task, 1 - index, group, width)
        points, vectors = cpo_points(plan, audit, audit_trials, tuple(dict.fromkeys((ADAPTIVE, fitted))))
        gepa, control_vector = gepa_point(plan, audit, audit_trials, control['setting'])
        accumulated[f'fold-{1 - index}'] = {ADAPTIVE: vectors[ADAPTIVE], FIXED: vectors[fitted],
                                            GEPA: control_vector}
        directions.append({'calibrationFold': index, 'auditFold': 1 - index, 'trials': len(trials),
                           'auditScoringRowsPerTrial': holdout_width, 'calibrationCpoMenu': totals,
                           'calibrationGepa': control, 'fixedSetting': fitted,
                           'audit': {ADAPTIVE: points[ADAPTIVE], FIXED: points[fitted], GEPA: gepa}})
    summed = {label: {key: sum(direction['audit'][label][key] for direction in directions) for key in METRICS}
              for label in (ADAPTIVE, FIXED, GEPA)}
    return {'directions': directions, 'auditTotals': summed,
            'pairedAudit': {peer: effects(accumulated, FIXED, peer, plan) for peer in (ADAPTIVE, GEPA)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, data = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    results = {}
    for subject in plan['datasets']:
        cells = transfer.math.load_cells(subject, data[subject]['record'])
        results[subject] = {f'{group}/{width}': measure(plan, subject, cells, group, width)
                            for group in plan['incumbentGroups'] for width in plan['challengerCounts']}
    result = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': results}
    with args.out.open('x') as out:
        out.write(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
