"""Transfer the frozen language-archive router and backup allocator to AIME and ARC."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
from itertools import pairwise
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import continuous_backup_allocation as allocation
from benchmarks import continuous_search_controls as simple
from benchmarks import recorded_two_witness_math_transfer as prior
from cpo._contract import digest
from cpo.joint_order_qualification import finish_joint_order
from cpo.optimizer import Row
from cpo.two_sided_certificate_cycle import _run


backup, joint, native, transfer = allocation.backup, allocation.joint, allocation.native, allocation.transfer
ROUTED, PAIRED, FUNDED, RETAIN = 'routed', 'joint-proof', 'task-balanced-backup', joint.RETAIN
STRICT = 'math-strict-cpo'
STRICT_REPORT = 'docs/recorded-math-validation-ties-results-v1.json'
STRICT_SHA = 'bf90d2fab3a9b33eece3a15392234db88afcaa13e5b8e2cf897ac54c9656e451'
POLICIES = (ROUTED, PAIRED, FUNDED)
METRICS = ('holdoutPasses', 'paidLookups')


def prepare(group, width):
    original, data = prior.math.prepare()
    learned, models, static = joint.adaptive.promotion.training_plan()
    fit = json.loads(transfer.read_locked(backup.FIT, backup.FIT_SHA))
    math_report = json.loads(transfer.read_locked(STRICT_REPORT, STRICT_SHA))
    discovery = {task for panel in fit['plan']['fitEnrollment'].values() for task, _ in panel}
    if (set(original['datasets']) & discovery or digest(fit['plan']) != fit['planSha256']
            or math_report['planSha256'] != digest(original)):
        raise ValueError('The math subjects must be disjoint and the proof fit and math plan verified')
    paths = (__file__, prior.__file__, *map(Path, (joint.__file__, allocation.__file__, backup.__file__,
                                                  joint.adaptive.__file__, native.__file__, native.gepa.__file__)))
    sources = {str(Path(path).relative_to(transfer.ROOT)): sha256(Path(path).read_bytes()).hexdigest() for path in paths}
    plan = {**{key: original[key] for key in ('datasets', 'corpusSha256', 'searchCap', 'gepaVersion',
                                             'bootstrapDraws', 'bootstrapSeed')},
            'protocol': 'recorded-math-router-transfer-v1', 'group': group, 'rosterWidth': width,
            'proofFitSha256': backup.FIT_SHA, 'routerFitSha256': learned['screenFitSha256'],
            'originalMathPlanSha256': digest(original), 'strictMathReceiptSha256': STRICT_SHA,
            'routerSearchCap': learned['fullRosterCap'],
            'sourceSha256': {**original['sourceSha256'], **joint.source_hashes(), **sources},
            'scope': 'Transfer the frozen language router and joint qualification order without refitting. '
                     'Use the original AIME and ARC seeds, splits and rosters. If joint proof ordering saves '
                     'lookups in aggregate, let the task-proportional one-probe allocator spend at most those '
                     'savings on terminal backups. Reproduce original strict math CPO. Compare each resulting '
                     'target price with simple and '
                     'split-safe GEPA sweeps. Report lookup counts and case-paired holdout effects.'}
    return plan, data, models, static, fit, math_report['results']


def accumulate(vector, held, grades):
    for case, grade in zip(held, grades, strict=True):
        vector[case] += grade


def record_native(target, paths, high):
    for lower, upper in pairwise((*paths, high + 1)):
        point, _, grades = paths[lower]
        if (point['searchLookups'] > lower or point['holdoutPasses'] != sum(grades)
                or point['paidLookups'] != point['searchLookups'] + point['qualificationLookups']):
            raise ValueError('Every split-safe GEPA path must fit its cap and paid ledger')
        cost = {key: point[key] for key in METRICS}
        target.setdefault(lower, Counter()).update(cost)
        target.setdefault(upper, Counter()).subtract(cost)


def native_settings(cells, trials, plan):
    width = len(trials[0][2][1])
    low_caps = {'full': width, 'half': width // 2}
    high = plan['searchCap']
    deltas = {}
    modes = native.gepa.native_cost.MODES
    with native.split_safe_cache():
        for start, roster, roles, seed in trials:
            for group, low in low_caps.items():
                args = native.validation_width((cells, start, roster, roles, seed), low)
                for mode in modes:
                    for rule, points in native.gepa.native_paths(args, mode, low, high).items():
                        record_native(deltas.setdefault((group, mode, rule), {}), points, high)
    totals = {RETAIN: {'holdoutPasses': sum(cells[start][case][0] for start, _, roles, _ in trials
                                           for case in roles[-1]), 'paidLookups': 0}}
    for (group, mode, rule), events in deltas.items():
        point = Counter()
        for cap in range(low_caps[group], high + 1):
            point.update(events.get(cap, {}))
            totals[f'{group}:{mode}/{cap}/{rule}'] = {key: point[key] for key in METRICS}
    return totals


def native_attainer(cells, trials, expected):
    setting = expected['setting']
    totals = Counter()
    vector = [0] * len(next(iter(cells.values())))
    with native.split_safe_cache():
        for start, roster, roles, seed in trials:
            held = roles[-1]
            if setting == RETAIN:
                grades = [cells[start][case][0] for case in held]
                totals['holdoutPasses'] += sum(grades)
            else:
                group, spec = setting.split(':', 1)
                mode, cap, rule = spec.split('/')
                width = len(roles[1]) // (2 if group == 'half' else 1)
                args = native.validation_width((cells, start, roster, roles, seed), width)
                point, _, grades = native.gepa.native_paths(args, mode, int(cap), int(cap))[rule][int(cap)]
                totals.update({key: point[key] for key in METRICS})
            accumulate(vector, held, grades)
    if any(totals[key] != expected[key] for key in METRICS):
        raise ValueError('The selected native setting must attain its measured score and price')
    return vector


def cpo_and_simple(plan, subject, cells, trials, models, static, priors):
    size = len(next(iter(cells.values())))
    cap = plan['routerSearchCap']
    runner = joint.adaptive.routed_runner({'fullRosterCap': cap}, models, static)
    proof = partial(finish_joint_order, priors=priors)
    run = native.paired.cycle.execute_path
    rows = len(trials[0][2][1])
    settings = {name: (partial(_run, screen=partial(simple.screen, mode=mode, width=width)), limit)
                for name, mode, width, limit in simple.settings(rows) if width <= plan['rosterWidth']}
    vectors = {name: [0] * size for name in (ROUTED, PAIRED, STRICT, RETAIN, *settings)}
    totals = {name: Counter() for name in vectors}
    episodes = []

    def add(name, grades, cases, price):
        totals[name].update(holdoutPasses=sum(grades), paidLookups=price)
        accumulate(vectors[name], cases, grades)

    for start, roster, roles, seed in trials:
        held = roles[-1]
        binary = {prompt: tuple(cell[0] for cell in cells[prompt]) for prompt in (start, *roster)}
        args = binary, start, roster, roles, seed
        original, paid = run(runner, *args, cap, 1)
        with patch.object(joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', proof):
            new, joint_paid = run(runner, *args, cap, 1)
            for name, (screen, limit) in settings.items():
                decision, ledger = run(screen, *args, limit, 1)
                add(name, [binary[decision.prompt][case] for case in held], held, len(ledger))
        if (original.search != new.search or original.prompt != new.prompt
                or joint.validation_reads(paid) != joint.validation_reads(joint_paid)):
            raise ValueError('Joint proof ordering must preserve nominations and deployments off the discovery archive')
        for name, prompt, spend in ((ROUTED, original.prompt, len(paid)), (PAIRED, new.prompt, len(joint_paid)),
                                    (RETAIN, start, 0)):
            add(name, [binary[prompt][case] for case in held], held, spend)
        archived, _, grades = prior.math.run_trial(cells, start, roster, roles, seed, 'strict', plan['searchCap'])
        add(STRICT, grades, held, archived['paidLookups'])
        finalist = new.search.finalist if new.qualification.status == 'rejected' else None
        initial = tuple(reply for reply in new.qualification.observations if reply.prompt == start)
        qualification = tuple(Row(str(case), 'qualification') for case in roles[2])
        episodes.append(backup.Episode(subject, seed, start, new.prompt, finalist, roster, qualification, tuple(held),
                                       binary, joint_paid, initial, rows))
    return episodes, totals, vectors


def measure(plan, data, models, static, fit, reference):
    priors = allocation.witness.previous.priors_of(fit)
    archives, all_episodes = {}, []
    for subject, layout in plan['datasets'].items():
        cells = prior.math.load_cells(subject, data[subject]['record'])
        trials = list(prior.trials(cells, layout, plan['group'], plan['rosterWidth']))
        episodes, points, vectors = cpo_and_simple(plan, subject, cells, trials, models, static, priors)
        original = reference[subject][f'{plan["group"]}/{plan["rosterWidth"]}']['totals']['strict']
        if any(points[STRICT][key] != original[key] for key in METRICS):
            raise ValueError('The prior strict math policy must reproduce its archived score and price')
        archives[subject] = cells, trials, points, vectors
        all_episodes.extend(episodes)
    saved = sum(points[ROUTED]['paidLookups'] - points[PAIRED]['paidLookups'] for _, _, points, _ in archives.values())
    funding = max(0, saved)
    offers = allocation.offers_for(backup.PROBE, all_episodes, priors)
    deployments, receipts = allocation.rollout(allocation.PROPORTIONAL, all_episodes, offers, funding, priors)
    for index, episode in enumerate(all_episodes):
        _, _, points, vectors = archives[episode.subject]
        prompt = deployments.get(index, episode.deployed)
        grades = [episode.cells[prompt][case] for case in episode.held]
        points.setdefault(FUNDED, Counter())['holdoutPasses'] += sum(grades)
        accumulate(vectors.setdefault(FUNDED, [0] * len(episode.cells[prompt])), episode.held, grades)

    compare = native.frozen.paired_effects.paired_effect
    results = {}
    for subject, (cells, trials, totals, vectors) in archives.items():
        totals[FUNDED]['paidLookups'] = totals[PAIRED]['paidLookups'] + receipts['lookupsByTask'][subject]
        available = native_settings(cells, trials, plan)
        native_labels = tuple(name for name in available if name != RETAIN)
        simpler = tuple(name for name in totals if name not in (*POLICIES, RETAIN, STRICT))
        curves, chosen = {}, {}
        for policy in POLICIES:
            budget = totals[policy]['paidLookups']
            best_native = native.gepa.best_fixed(available, native_labels, budget)
            best_simple = native.gepa.best_fixed(totals, simpler, budget)
            setting = best_native['setting']
            if setting not in chosen:
                chosen[setting] = native_attainer(cells, trials, best_native)
            vectors['gepa'], vectors['simple'] = chosen[setting], vectors[best_simple['setting']]
            curves[policy] = {'bestGepa': best_native, 'bestSimple': best_simple,
                              'paired': {method: compare({subject: vectors}, policy, method, plan)
                                         for method in ('gepa', 'simple', ROUTED, PAIRED, STRICT)}}
        results[subject] = {'episodes': len(trials), 'policies': {name: totals[name] for name in (*POLICIES, STRICT)},
                            'controls': curves, 'splitSafeGepaSettings': len(native_labels),
                            'simpleSettings': len(simpler)}
    return {'math': results, 'jointProofLookupSavings': saved, 'backupLimit': funding, 'backup': receipts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=('root', 'rotated'), required=True)
    parser.add_argument('--width', type=int, choices=(4, 8), required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.group, args.width)
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
