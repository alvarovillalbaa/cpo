"""Reprice exact archived alternatives at CPO's realized audit spend."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import quoted_schedule_guarded_transfer as guard
from cpo._contract import digest
from cpo.two_sided_certificate_cycle import _run


parent = guard.parent
native, transfer, adaptive = parent.native, parent.transfer, parent.adaptive
continuous, RETAIN = parent.continuous, parent.RETAIN
GEPA, EAGER, QUOTED = 'native-gepa', 'eager-simple', 'quoted-simple'
POLICIES = (guard.GUARDED, guard.QUOTED, guard.PREFIX)
RECEIPTS = dict(zip(parent.discovery.COHORTS, (
    'c61ab1af2d979ae52f922fe29519b00b0d334c820cd35af059ede86cd4460b20',
    'fa7d810c995fdae9f4a1b0ee235d3d5eff05ecefa6b0db546918f8ec33ad6866',
    'd57722622bad2d82bc775af68146a06df256d7f017fcbc4050087bc313813499',
    'f13b55e8bd62d2355d209541811c3dafa4424b7ce3eef3766cce1b6b17ff0556',
    '67b1b735f8af7578882f4774b28e15b557a131fe44c030b5126752aeef02c925',
    'f2772f76598dfe4c3c9cc999c32247dc5b27c90cc6b3d28d4f40c52ad0929e4c',
    'e9c3b9eb12ec72c0d9f2e94f58dfce5391ce2bca1d54b17ce54bd5be7ad7f136',
), strict=True))


def prepare(cohort):
    base, tasks, _, _, frozen, checkpoint = guard.prepare(cohort)
    lock = RECEIPTS[cohort]
    name = f'docs/quoted-schedule-guarded-transfer-{cohort.lower()}-v1.json'
    receipt = json.loads(transfer.read_locked(name, lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('The realized budget frontier must use the exact original audit')
    source = Path(__file__).resolve()
    plan = {**base, 'protocol': 'quoted-schedule-realized-frontier-v1', 'guardReceiptSha256': lock,
            'sourceSha256': {**base['sourceSha256'], str(source.relative_to(transfer.ROOT)):
                             sha256(source.read_bytes()).hexdigest()},
            'fullNativeCap': base['searchCap'], 'pricedPolicies': POLICIES,
            'scope': 'Keep the audit model, seeds, three-cycle rosters and scoring cases unchanged. '
                     'Sweep the complete native GEPA grid through 180 and both original simple menus, '
                     'using eager and quoted prices on the same simple settings. Match the actual budget '
                     'of the guarded, task-specific and frozen CPO policies. Check both a single fixed '
                     'setting and an exact pooled optimum allowed to choose a setting per audit direction. '
                     'Directly replay every selected fixed and direction-specific schedule.'}
    return plan, tasks, frozen, checkpoint, receipt['results']


def optimum_by_budget(points, budgets):
    labels = tuple(name for name in next(iter(points.values())) if name != RETAIN)
    totals = {name: Counter() for name in (*labels, RETAIN)}
    for direction in points.values():
        for name, point in direction.items():
            totals[name].update(point)
    common = {name: native.gepa.best_fixed(totals, labels, budget) for name, budget in budgets.items()}
    ceiling = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    mixed = ceiling(points, labels, budgets)
    return {name: {'common': {**point, 'settingsByDirection': dict.fromkeys(points, point['setting'])},
                   'mixed': {'holdoutPasses': mixed[name]['holdoutPasses'],
                             'paidLookups': mixed[name]['paidLookups'],
                             'settingsByDirection': mixed[name]['settingsBySubject']}}
            for name, point in common.items()}


def native_rollout(packed, current, stages, setting):
    cost = 0
    for seed, roster, roles in stages:
        current, grades, paid = continuous.attaining_trial(setting, (packed, current, roster, roles, seed))
        cost += paid
    return cost, grades


def capture(plan, tasks, frozen, checkpoint, reference):
    quote, eager = parent.discovery.screens_with_quotes(plan), adaptive.screens(plan)
    prefix = partial(adaptive.cycle, actions=tuple(quote[action] for action in frozen))
    engines = {label: {name: partial(_run, screen=screens[name]) for name, *_ in plan['controls']}
               for label, screens in ((QUOTED, quote), (EAGER, eager))}
    for entries in engines.values():
        entries[RETAIN] = None
    decks = {label: {} for label in (QUOTED, EAGER, GEPA)}
    inputs, vectors = {}, {}
    for subject, entries in reference['directions'].items():
        for old, row in zip(checkpoint['directions'][subject], entries, strict=True):
            if (old['auditModel'], old['auditFold']) != (row['auditModel'], row['auditFold']):
                raise ValueError('The old and guarded controls must use the same audit direction')
            fold = row['auditFold']
            name = f'{subject}/{fold}'
            matrix = tasks[subject][row['auditModel']]
            held = plan['pairs'][subject]['folds'][fold]
            cells, packed = transfer.case_cells(matrix)
            stages = tuple(parent.layouts(plan, subject, matrix, plan['auditSeeds'], held))
            inputs[name] = cells, packed, stages, len(held)
            original_quotes = engines[QUOTED]
            runners = {guard.PREFIX: prefix, guard.QUOTED: original_quotes[old['calibrationSetting'][guard.QUOTED]['setting']],
                       guard.GUARDED: original_quotes[row['selected']['setting']] if row['switched'] else prefix}
            totals, vectors[name] = guard.score(plan, subject, matrix, held, plan['auditSeeds'], runners)
            if any(point != row['audit'][label] for label, point in totals.items()):
                raise ValueError('Each priced CPO policy must reproduce its original held-out score and price')
            for label, settings in engines.items():
                decks[label][name], _ = guard.score(plan, subject, matrix, held, plan['auditSeeds'], settings)
            retained = decks[EAGER][name][RETAIN]
            first, last = {}, {}
            cap = plan['fullNativeCap']
            with native.split_safe_cache():
                for start, cycle in stages:
                    continuous.native_episode(packed, start, cycle, cap, first, last)
            decks[GEPA][name] = {RETAIN: retained}
            transfer.tally_native(decks[GEPA][name], last, cap)
    return decks, inputs, vectors, engines


def replay_attainers(plan, schedules, decks, inputs, vectors, engines):
    paid = {name: Counter() for name in schedules}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for direction, (cells, packed, episodes, size) in inputs.items():
        requested = {(menu, point['settingsByDirection'][direction]) for menu, point in schedules.values()}
        results = {}
        for menu, setting in sorted(requested):
            point, grades = Counter(), [0] * size
            for start, cycle in episodes:
                if menu == GEPA:
                    cost, held = native_rollout(packed, start, cycle, setting)
                else:
                    cost, held = parent.rollout(cells, start, cycle, engines[menu][setting], plan['nativeSearchCap'])
                point.update(holdoutPasses=sum(held), paidLookups=cost)
                add(grades, held)
            if point != decks[menu][direction][setting]:
                raise ValueError('Direct replay must attain every selected audit setting at its recorded price')
            results[menu, setting] = point, grades
        for name, (menu, point) in schedules.items():
            observed, grades = results[menu, point['settingsByDirection'][direction]]
            paid[name].update(observed)
            vectors[direction][name] = grades
    if any(paid[name] != {key: point[key] for key in ('holdoutPasses', 'paidLookups')}
           for name, (_, point) in schedules.items()):
        raise ValueError('The per-direction attainers must reconcile to the exact pooled optimum')


def measure(plan, tasks, frozen, checkpoint, reference):
    decks, inputs, vectors, engines = capture(plan, tasks, frozen, checkpoint, reference)
    policies = {label: reference['auditTotals'][label] for label in POLICIES}
    budgets = {name: point['paidLookups'] for name, point in policies.items()}
    optima = {name: optimum_by_budget(points, budgets) for name, points in decks.items()}
    schedules = {f'{policy}/{menu}/{scope}': (menu, point)
                 for menu, outputs in optima.items() for policy, scopes in outputs.items() for scope, point in scopes.items()}
    replay_attainers(plan, schedules, decks, inputs, vectors, engines)
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for policy in POLICIES:
        comparisons[policy] = {menu: {scope: {**point, 'pairedAgainstCpo': paired(
            vectors, f'{policy}/{menu}/{scope}', policy, plan,
        )} for scope, point in output[policy].items()} for menu, output in optima.items()}
    return {'auditEpisodes': reference['auditEpisodes'], 'pricedPolicies': policies, 'comparisons': comparisons,
            'menuSettings': {name: len(next(iter(points.values()))) for name, points in decks.items()},
            'directionMenuSha256': {name: digest(points) for name, points in decks.items()}}


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
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': measure(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
