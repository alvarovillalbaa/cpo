"""Transfer the frozen four-challenger math policy to archived language tasks."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import continuous_archive_backup as backup
from benchmarks import recorded_math_reinvested_halving as math
from cpo._contract import digest
from cpo.joint_order_qualification import finish_joint_order
from cpo.reinvested_shared_validation_cycle import _screen, run_reinvested_shared_validation_cycle
from cpo.two_sided_certificate_cycle import _run


joint = backup.joint
adaptive, continuous, native, transfer = joint.adaptive, joint.continuous, joint.native, joint.transfer
controls, promotion = adaptive.controls, adaptive.promotion
ROUTED, RETAIN = adaptive.ROUTED, adaptive.RETAIN
CANDIDATE, PUBLIC, QUOTED, EAGER = 'reinvested-joint', 'reinvested-public', 'quoted-halving', 'eager-halving'
METHODS = (CANDIDATE, PUBLIC, QUOTED, EAGER)
METRICS = ('holdoutPasses', 'paidLookups')
MATH_SHA = '37e0cdfdcedf517a58791d7ff63d3dc881994b3844c7434bc3ce93a40e6b9ea8'


def full_round_quote(width, rows):
    cost = 0
    for depth in range(1, rows + 1):
        cost += width + 1
        if depth in controls.RUNGS:
            width = (width + 1) // 2
    return cost


def prepare(cohort):
    fit_bytes = transfer.read_locked(backup.FIT, backup.FIT_SHA)
    base, panels, models, static, fit, gepa, simple = joint.prepare(cohort, fit_bytes)
    eligible = {subject for subject, _, _ in panels}
    discovery = {subject for group in fit['plan']['fitEnrollment'].values() for subject, _ in group}
    if eligible & (discovery | {'aime', 'arc'}):
        raise ValueError('Transfer cannot include math or qualification discovery tasks')
    receipt = json.loads(transfer.read_locked('docs/recorded-math-reinvested-halving-rotated-4-v1.json', MATH_SHA))
    arc = receipt['results']['arc']['directions']
    settings = {entry['calibrationChoice']['setting'] for entry in arc if entry['expandedChoseNew']}
    if len(arc) != 2 or not all(entry['expandedChoseNew'] for entry in arc) or settings != {f'{math.ARM}/4/19'}:
        raise ValueError('Both ARC-AGI calibration folds must have selected the frozen setting')
    files = (Path(__file__).resolve(), Path(math.__file__), Path(controls.__file__),
             transfer.ROOT / 'cpo/reinvested_shared_validation_cycle.py')
    sources = {str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest() for path in files}
    rows = base['caseCounts'][1]
    full_quote = full_round_quote(4, rows)
    plan = {**base, 'protocol': 'reinvested-halving-language-transfer-v1', 'mathReceiptSha256': MATH_SHA,
            'subjects': sorted(eligible), 'halvingWidth': 4, 'halvingCap': 19,
            'controls': list(controls.settings(rows)),
            'diagnostics': {'one-slot-below-full-quote': {'width': 4, 'cap': full_quote - 1},
                            'full-roster-at-original-cap': {'width': base['challengers'], 'cap': 19}},
            'sourceSha256': {**base['sourceSha256'], **sources},
            'scope': 'Transfer the math setting unchanged with its task-disjoint fitted qualification order. '
                     'Carry each deployed prompt through the three existing language cycles. Isolate reuse '
                     'against identical certified halving at the same configured cap and replay the public '
                     'qualification order. Compare all simple controls at the realized math-policy price and '
                     'replay both affordable native attainers from the locked full-grid anchors. '
                     'Report native budget bounds when the published points do not identify the exact optimum. '
                     'Also audit the reuse mechanism at two geometry-defined settings where the eager cap '
                     'can bind: one lookup below the narrow full-panel quote, and the entire roster at 19.'}
    priors = {tuple(map(int, key.split('/'))) if key != 'pooled' else None: values
              for key, values in fit['weights'].items()}
    return plan, panels, models, static, priors, gepa, simple


def replay_fixed(plan, panels, priors, vectors, *, width, cap):
    proof = partial(finish_joint_order, priors=priors)
    plain = joint.ORIGINAL_FINISH
    quoted = partial(_run, screen=partial(_screen, reinvest=False))
    eager = partial(_run, screen=partial(controls.screen, mode=controls.HALVING, width=width))
    engines = {CANDIDATE: run_reinvested_shared_validation_cycle, PUBLIC: run_reinvested_shared_validation_cycle,
               QUOTED: quoted, EAGER: eager}
    run = native.paired.cycle.execute_path
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    totals = {method: Counter() for method in METHODS}
    hashes = {}
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        traces = {method: [] for method in METHODS}
        for seed in plan['seeds']:
            start, cycles = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            held = cycles[0][2][-1]
            current = dict.fromkeys(METHODS, start)
            for local_seed, roster, roles in cycles:
                decisions, paid = {}, {}
                for name, engine in engines.items():
                    before = current[name]
                    with patch.object(joint.two_sided_certificate_cycle, '_finish_with_partner_evidence',
                                      plain if name == PUBLIC else proof):
                        result, ledger = run(engine, cells, before, roster[:width], roles, local_seed, cap, 1)
                    continuous.routing.verify_qualification(cells, before, roles, result, ledger, 1)
                    decisions[name], paid[name] = result, ledger
                    rounds = sum(role == 'validation' and prompt == before for role, prompt, _ in ledger)
                    totals[name].update(paidLookups=len(ledger), validationRounds=rounds, promotions=int(result.promoted))
                    traces[name].append((before, result.prompt, result.search.finalist, list(ledger.items())))
                    current[name] = result.prompt
                if (decisions[QUOTED].search.finalist != decisions[EAGER].search.finalist
                        or decisions[QUOTED].qualification != decisions[EAGER].qualification
                        or not paid[QUOTED].keys() <= paid[EAGER].keys()):
                    raise ValueError('Without reuse, read skipping must preserve eager halving')
                if (decisions[CANDIDATE].search != decisions[PUBLIC].search
                        or current[CANDIDATE] != current[PUBLIC]
                        or joint.validation_reads(paid[CANDIDATE]) != joint.validation_reads(paid[PUBLIC])):
                    raise ValueError('Proof ordering can only change qualification callback order and cost')
            for name, deployed in current.items():
                grades = [cells[deployed][case] for case in held]
                totals[name].update(holdoutPasses=sum(grades))
                scores = vectors.setdefault(subject, {})
                add(scores.setdefault(name, [0] * len(held)), grades)
        hashes[f'{subject}/{model}'] = {name: digest(trace) for name, trace in traces.items()}
    return totals, hashes


def compare_simple(plan, panels, simple, budget, vectors):
    menu = simple['settingsTotals']
    labels = tuple(name for name in menu if name != RETAIN)
    matches = {mode: native.gepa.best_fixed(menu, [name for name in labels if name.startswith(f'{mode}/')], budget)
               for mode in controls.MODES}
    ceiling = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    tuned = ceiling(simple['settingsBySubject'], labels, {CANDIDATE: budget})[CANDIDATE]
    schedules = {mode: dict.fromkeys(plan['subjects'], point['setting']) for mode, point in matches.items()}
    schedules['subject-tuned-simple'] = tuned['settingsBySubject']
    screens = adaptive.screens(plan)
    runners = {name: partial(_run, screen=screens[name]) for name in labels}
    points, _ = adaptive.replay(plan, panels, runners, schedules, vectors)
    matched = {**matches, 'subject-tuned-simple': tuned}
    if any(points[name] != {key: point[key] for key in METRICS} for name, point in matched.items()):
        raise ValueError('Every matched simple setting must attain the locked score and price')
    return matched


def compare_native(plan, panels, gepa, budget, retention, vectors):
    named = {'common-gepa': 'bestCommonGepa', 'subject-tuned-gepa': 'subjectTunedGepa'}
    bounds = {name: promotion.budget_bounds(gepa[key], gepa['cpo'], budget, retention) for name, key in named.items()}
    schedules = {}
    for name, bound in bounds.items():
        point = bound['attainer'] or {}
        schedules[name] = point.get('settingsBySubject') or dict.fromkeys(plan['subjects'], point.get('setting', RETAIN))
    actual = promotion.compare_native(panels, plan, vectors, schedules)
    for name, point in actual.items():
        if (point['holdoutPasses'] != bounds[name]['lowerPasses'] or point['paidLookups'] > budget
                or point['paidLookups'] != (bounds[name]['attainer'] or {'paidLookups': 0})['paidLookups']):
            raise ValueError('An affordable native anchor must attain its reported score and spend')
    return bounds, actual


def measure(plan, panels, models, static, priors, gepa, simple):
    vectors = {}
    totals, paths = replay_fixed(plan, panels, priors, vectors, width=plan['halvingWidth'], cap=plan['halvingCap'])
    router = adaptive.routed_runner(plan, models, static)
    expected = {ROUTED: dict.fromkeys(plan['subjects'], ROUTED)}
    routed, hashes = adaptive.replay(plan, panels, {ROUTED: router}, expected, vectors)
    if routed[ROUTED] != simple['cpo'][ROUTED] or any(
            hashes[panel][ROUTED] != point[ROUTED] for panel, point in simple['cpoTrajectoryHashes'].items()):
        raise ValueError('The established router must reproduce its paid paths')
    budget = totals[CANDIDATE]['paidLookups']
    matched = compare_simple(plan, panels, simple, budget, vectors)
    bounds, actual = compare_native(plan, panels, gepa, budget, simple['settingsTotals'][RETAIN]['holdoutPasses'], vectors)
    paired = native.frozen.paired_effects.paired_effect
    effects = {name: paired(vectors, CANDIDATE, name, plan)
               for name in (PUBLIC, QUOTED, EAGER, ROUTED, *matched, *actual)}
    diagnostics = {}
    for label, setting in plan['diagnostics'].items():
        scores = {}
        points, hashes = replay_fixed(plan, panels, priors, scores, **setting)
        controls_at_price = compare_simple(plan, panels, simple, points[CANDIDATE]['paidLookups'], scores)
        diagnostics[label] = {'policies': points, 'trajectoryHashes': hashes,
                              'simpleAtCandidateBudget': controls_at_price,
                              'paired': {name: paired(scores, CANDIDATE, name, plan)
                                         for name in (QUOTED, 'subject-tuned-simple')}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': {**totals, **routed}, 'trajectoryHashes': paths,
            'simpleAtCandidateBudget': matched, 'nativeBoundsAtCandidateBudget': bounds,
            'replayedNativeAnchors': actual, 'paired': effects, 'bindingCapDiagnostics': diagnostics}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=continuous.COHORTS, required=True)
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
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
