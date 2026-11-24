"""Test whether higher primary-search allowances recover math archive quality."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_math_router_transfer as previous
from cpo._contract import digest
from cpo.joint_order_qualification import finish_joint_order
from cpo.paired_order_certificate_cycle import run_paired_order_certificate_cycle
from cpo.two_sided_certificate_cycle import _run


native, transfer, joint = previous.native, previous.transfer, previous.joint
ROUTED, STRICT, RETAIN = previous.ROUTED, previous.STRICT, previous.RETAIN
STATIC, DEFERRED = 'fixed-screen', 'paired-certificate'
FAMILIES = (ROUTED, STATIC, DEFERRED, STRICT)
RECEIPTS = {
    'root/4': 'c190265f64643750e60e8109ad40b6ffd1fefe0f74f25c7de31e555b80ab39db',
    'root/8': '36000b42abbcb190761fdf8fa55925fdded20a43077eac6dc55b050fe5cf8e1f',
    'rotated/4': '53f3d0c02287f18f5a02328c2c1ed3d5355813f713a85a42633d3c62edeed180',
    'rotated/8': 'f7f45910bf62f5a56fc18bd28b04339ee8a73932016c0b2e3f2015c4792f104b',
}


def prepare(group, width):
    base, data, models, static, fit, _ = previous.prepare(group, width)
    lock = RECEIPTS[f'{group}/{width}']
    path = f'docs/recorded-math-router-transfer-{group}-{width}-v1.json'
    receipt = json.loads(transfer.read_locked(path, lock))
    if receipt['planSha256'] != digest(base):
        raise ValueError('The frozen router, roster and math cases must match the prior replay')
    sources = {str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest()
               for path in (Path(__file__), Path(previous.__file__),
                            transfer.ROOT / 'cpo/paired_order_certificate_cycle.py',
                            transfer.ROOT / 'cpo/deferred_certificate_cycle.py')}
    plan = {**base, 'protocol': 'recorded-math-router-frontier-v1', 'mathTransferSha256': lock,
            'sourceSha256': {**base['sourceSha256'], **sources}, 'cpoFamilies': FAMILIES,
            'scope': 'Sweep every integer CPO search cap from one validation panel to the full unique '
                     'incumbent-and-challenger validation matrix, plus the previous 180-read strict policy. '
                     'Compare the frozen router, its fitted fixed screen, paired certificate and strict math '
                     'CPO. Reproduce the routed 19-read and strict 180-read anchors and keep all qualification '
                     'and holdout cases fixed. Compare at the actual 19-read router cost, the midpoint to the '
                     'strict price and the original strict price. Reuse the split-safe native and simple sweeps.'}
    return plan, data, models, static, fit, receipt['results']['math']


def anchor_budgets(router, strict):
    if router > strict:
        raise ValueError('The router anchor should be cheaper than the strict policy')
    return {'router-price': router, 'midpoint-price': (router + strict) // 2, 'strict-price': strict}


def sweep_cpo(plan, cells, trials, models, static, priors):
    routes = joint.adaptive.promotion.runner_map(models, static)
    runs = {ROUTED: routes[joint.ROUTED], STATIC: routes[joint.adaptive.continuous.STATIC],
            DEFERRED: run_paired_order_certificate_cycle}
    width = len(trials[0][2][1])
    full = width * (1 + plan['rosterWidth'])
    caps = tuple(range(width, full + 1))
    cases = len(next(iter(cells.values())))
    simple = previous.simple
    controls = {name: (partial(_run, screen=partial(simple.screen, mode=mode, width=roster)), limit)
                for name, mode, roster, limit in simple.settings(width) if roster <= plan['rosterWidth']}
    cpo = [f'{family}/{cap}' for family in FAMILIES for cap in caps]
    old_strict = f'{STRICT}/{plan["searchCap"]}'
    totals = {name: Counter() for name in (*cpo, old_strict, RETAIN, *controls)}
    vectors = {name: [0] * cases for name in totals}
    proof = partial(finish_joint_order, priors=priors)
    binary = {prompt: tuple(cell[0] for cell in row) for prompt, row in cells.items()}
    run = native.paired.cycle.execute_path

    def add(name, held, grades, paid):
        totals[name].update(holdoutPasses=sum(grades), paidLookups=paid)
        previous.accumulate(vectors[name], held, grades)

    for start, roster, roles, seed in trials:
        held = roles[-1]
        args = binary, start, roster, roles, seed
        add(RETAIN, held, [binary[start][case] for case in held], 0)
        for family, runner in runs.items():
            for cap in caps:
                result, ledger = run(runner, *args, cap, 1)
                joint.continuous.routing.verify_qualification(binary, start, roles, result, ledger, 1)
                add(f'{family}/{cap}', held, [binary[result.prompt][case] for case in held], len(ledger))
        for cap in (*caps, plan['searchCap']):
            point, _, grades = previous.prior.math.run_trial(cells, start, roster, roles, seed, 'strict', cap)
            add(f'{STRICT}/{cap}', held, grades, point['paidLookups'])
        with patch.object(joint.two_sided_certificate_cycle, '_finish_with_partner_evidence', proof):
            for name, (runner, cap) in controls.items():
                result, ledger = run(runner, *args, cap, 1)
                add(name, held, [binary[result.prompt][case] for case in held], len(ledger))
    return totals, vectors, (*cpo, old_strict), tuple(controls)


def compare(plan, subject, cells, trials, totals, vectors, cpo, simple, reference):
    root = f'{ROUTED}/{plan["routerSearchCap"]}'
    strict = f'{STRICT}/{plan["searchCap"]}'
    if totals[root] != reference['policies'][ROUTED] or totals[strict] != reference['policies'][STRICT]:
        raise ValueError('The prior routed and strict anchors must reproduce exactly')
    native_totals = previous.native_settings(cells, trials, plan)
    native_labels = tuple(name for name in native_totals if name != RETAIN)
    budgets = anchor_budgets(totals[root]['paidLookups'], totals[strict]['paidLookups'])
    effects = native.frozen.paired_effects.paired_effect
    attainers, summary = {}, {}
    prior_match = reference['controls'][ROUTED]
    for label, budget in budgets.items():
        match = {name: native.gepa.best_fixed(totals, [arm for arm in cpo if arm.startswith(f'{name}/')], budget)
                 for name in FAMILIES}
        inexpensive = native.gepa.best_fixed(totals, simple, budget)
        gepa = native.gepa.best_fixed(native_totals, native_labels, budget)
        if label == 'router-price' and (gepa != prior_match['bestGepa'] or inexpensive != prior_match['bestSimple']):
            raise ValueError('The prior native and simple settings must reproduce at the original router price')
        setting = gepa['setting']
        if setting not in attainers:
            attainers[setting] = previous.native_attainer(cells, trials, gepa)
        vectors['gepa'], vectors['simple'] = attainers[setting], vectors[inexpensive['setting']]
        best = native.gepa.best_fixed(totals, cpo, budget)
        candidate = best['setting']
        summary[label] = {'ceilingLookups': budget, 'bestByFamily': match, 'bestCpo': best,
                          'bestGepa': gepa, 'bestSimple': inexpensive,
                          'pairedBestCpo': {control: effects({subject: vectors}, candidate, control, plan)
                                            for control in ('gepa', 'simple', root, strict)}}
    return {'episodes': len(trials), 'anchors': {name: totals[name] for name in (root, strict, RETAIN)},
            'cpoSettings': {name: totals[name] for name in cpo}, 'lookupBudgetComparisons': summary,
            'nativeSettings': len(native_labels), 'simpleSettings': len(simple)}


def measure(plan, data, models, static, fit, reference):
    priors = previous.allocation.witness.previous.priors_of(fit)
    results = {}
    for subject, layout in plan['datasets'].items():
        cells = previous.prior.math.load_cells(subject, data[subject]['record'])
        trials = list(previous.prior.trials(cells, layout, plan['group'], plan['rosterWidth']))
        totals, vectors, cpo, simple = sweep_cpo(plan, cells, trials, models, static, priors)
        results[subject] = compare(plan, subject, cells, trials, totals, vectors, cpo, simple,
                                   reference[subject])
    return results


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
