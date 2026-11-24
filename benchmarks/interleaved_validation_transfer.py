"""Attribute the effect of switching validation cases and test interleaving."""

import argparse
from collections import Counter
from functools import cache, partial
from hashlib import sha256
from importlib.metadata import version
from itertools import product
import json
from pathlib import Path

from benchmarks import switch_validation_case_transfer as switch
from cpo._contract import digest
from cpo.interleaved_validation_cases import screen
from cpo.qualification_prefix_cycle import run_qualification_prefix_cycle
from cpo.two_sided_certificate_cycle import _run


bounded, discovery, adaptive = switch.bounded, switch.discovery, switch.adaptive
depth, parent, native, transfer = switch.depth, switch.parent, switch.native, switch.transfer
BOUNDED, SWITCH, ROUTER = switch.BOUNDED, switch.FIXED, switch.ROUTER
FIT, FIRST, SECOND = 'fitted-interleave', 'opening-case-first', 'second-case-first'
FIT_SHA = '98fb54beaf1660bf4b4f9e59c1c4a6d44333d65445be4c8359e0612f3af107ff'
LOCKS = dict(zip(discovery.COHORTS, (
    '420b69ebafb8f61537628816272e91df8c498bcb1dabb3485e89d410add9bf0c',
    'b3716559505ad5c3dd68891f36b51e150aa202b96216c218162bd1a03c001a61',
    '5f702dcb51e3156ddf90f0c3fe3dcb386e2380850765493cc58bd1c3609bcad8',
    '0b322cb461cbbb73a69b1083ab45895eba755329d5e06bb8037314f174ce88bf',
    '49ffcf74bb37d86e527c3dadab72b1b00776fb331c5409110715dca35a17790d',
    '52d38270c4ef1b30a5f30cdf38960f33593541f0672dc4d0f3e0bed63eff560b',
    '000b9b176aff8edcae585bececa086292655f4b6cfb866e079da794f4d0e724e',
), strict=True))


def contract():
    prior = switch.contract()
    original = prior[0]
    fit = json.loads(transfer.read_locked('docs/switch-validation-case-fit-v1.json', FIT_SHA))
    if digest(original) != fit['planSha256'] or digest(fit['plan']) != fit['planSha256']:
        raise ValueError('The previous discovery plan must reproduce')
    reference = tuple(original['boundedActions'])
    spaces = tuple(dict.fromkeys((*reference[1:], original['fixedSwitchAction'], FIRST, SECOND)))
    root = transfer.ROOT
    files = (Path(__file__).resolve(), root / 'cpo/interleaved_validation_cases.py')
    plan = {**original, 'protocol': 'interleaved-validation-fit-v1', 'switchFitSha256': FIT_SHA,
            'choices': spaces, 'sourceSha256': {**original['sourceSha256'],
                                              **{str(file.relative_to(root)): sha256(file.read_bytes()).hexdigest()
                                                 for file in files}},
            'scope': 'Keep the first-position incumbent-first action. Compare the bounded opening, '
                     'the fixed switch after two and both interleavings. Fit only on the same disjoint '
                     'discovery tasks within the existing router budget for each cohort.'}
    return plan, prior, fit


def limited(incumbent, candidates, rows, evaluate, cap, *, width, maximum, second_first):
    return screen(incumbent, candidates[:width], rows, evaluate, min(cap, maximum), second_first=second_first)


def options(plan):
    return {**switch.screens(plan), **{name: partial(limited, width=plan['width'], maximum=plan['cap'],
                                                      second_first=name == SECOND) for name in (FIRST, SECOND)}}


def fit(plan, prior_fit, groups):
    reference = tuple(plan['boundedActions'])
    menu = [(reference[0], *tail) for tail in product(plan['choices'], repeat=len(reference) - 1)]
    engines = {name: partial(_run, screen=action) for name, action in options(plan).items()}
    points = depth.sweep(plan, groups, menu, engines)
    previous = (reference[0],) + (plan['fixedSwitchAction'],) * (len(reference) - 1)
    if points[reference] != prior_fit['boundedOpening'] or points[previous] != prior_fit['fixedSwitch']:
        raise ValueError('Both earlier discovery scores and prices must reproduce')
    caps = prior_fit['policies'][switch.FITTED]['budgets']
    selected = bounded.choose(points, caps, reference)
    fixed = {name: points[(reference[0],) + (name,) * (len(reference) - 1)] for name in (FIRST, SECOND)}
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0,
            'selected': selected, 'interleavingControls': fixed, 'tested': len(points),
            'menuSha256': digest({'|'.join(table): totals for table, totals in points.items()})}


def target(cohort, plan, prior, previous_fit, fitted):
    if fitted['planSha256'] != digest(plan) or digest(fitted['plan']) != digest(plan):
        raise ValueError('Target replay requires the sealed fit')
    inherited, inputs = switch.target(cohort, *prior, previous_fit)
    lock = LOCKS[cohort]
    receipt = json.loads(transfer.read_locked(f'docs/switch-validation-case-transfer-{cohort.lower()}-v1.json', lock))
    if digest(inherited) != receipt['planSha256']:
        raise ValueError('The prior switch target plan must reproduce')
    base = inherited['actions'][BOUNDED]
    selected = fitted['selected']['actions']
    if len(selected) != len(base) or selected[0] != base[0] or set(selected[1:]) - set(plan['choices']):
        raise ValueError('Every fitted action must be in the discovery menu')
    actions = {BOUNDED: base, SWITCH: inherited['actions'][SWITCH], FIT: selected,
               **{name: (base[0],) + (name,) * (len(base) - 1) for name in (FIRST, SECOND)}}
    target_plan = {**inherited, 'protocol': 'interleaved-validation-transfer-v1', 'actions': actions,
                   'fitReceiptSha256': digest(fitted), 'switchTransferSha256': lock,
                   'sourceSha256': {**inherited['sourceSha256'], **plan['sourceSha256']},
                   'scope': 'Reproduce the bounded opening and fixed switch. Compare the fitted schedule '
                            'and both fixed interleavings at actual spend. Attribute their differences by '
                            'replacing one more leading cycle at a time against the bounded opening.'}
    return target_plan, (*inputs[:-1], receipt['results'])


def channel(incumbent, baseline, treatment, ledger, validation):
    if baseline == treatment:
        return 'same-deployment'
    if treatment == incumbent:
        return 'lost-opening-repair'
    if ledger.get(('validation', treatment, str(validation[0]))) is True:
        evidence = 'opening'
    elif ledger.get(('validation', treatment, str(validation[1]))) is True:
        evidence = 'second-case'
    else:
        raise ValueError('A changed deployment must have a paid validation repair')
    return f'added-{evidence}-repair' if baseline == incumbent else f'replaced-with-{evidence}-repair'


def episode(cells, stages, start, runners, cap):
    run = native.paired.cycle.execute_path
    held = stages[0][2][-1]

    @cache
    def step(index, incumbent, arm):
        seed, roster, roles = stages[index]
        result, ledger = run(runners[arm], cells, incumbent, roster, roles, seed, cap, 1)
        depth.continuous.routing.verify_qualification(cells, incumbent, roles, result, ledger, 1)
        return result.prompt, ledger

    @cache
    def suffix(index, incumbent):
        if index == len(stages):
            return sum(cells[incumbent][case] for case in held), 0
        chosen, values = step(index, incumbent, BOUNDED)
        passes, cost = suffix(index + 1, chosen)
        return passes, cost + len(values)

    before = suffix(0, start)
    results, changes = {BOUNDED: before}, {}
    for arm in (SWITCH, FIRST, SECOND):
        current, cumulative = start, 0
        old_passes, old_cost = before
        bins = {}
        for index, (_, _, roles) in enumerate(stages):
            baseline, _ = step(index, current, BOUNDED)
            chosen, ledger = step(index, current, arm)
            reason = channel(current, baseline, chosen, ledger, roles[1])
            cumulative += len(ledger)
            passes, tail_cost = suffix(index + 1, chosen)
            cost = cumulative + tail_cost
            bins.setdefault(reason, Counter()).update(cycles=1, passes=passes - old_passes, lookups=cost - old_cost)
            current, old_passes, old_cost = chosen, passes, cost
        changes[arm] = bins
        results[arm] = old_passes, old_cost
    step.cache_clear()
    suffix.cache_clear()
    return results, changes


def attribute(plan, panels, runners, totals):
    costs = max(cap for _, _, _, cap in plan['controls'])
    arms = (SWITCH, FIRST, SECOND)
    measured = {name: Counter() for name in (BOUNDED, *arms)}
    changes = {name: {} for name in arms}
    for subject, _, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        for seed in plan['seeds']:
            start, stages = depth.continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            outcomes, grouping = episode(cells, stages, start, runners, costs)
            for name, (passes, cost) in outcomes.items():
                measured[name].update(holdoutPasses=passes, paidLookups=cost)
            for name, bins in grouping.items():
                for key, point in bins.items():
                    changes[name].setdefault(key, Counter()).update(point)
    if any(total != totals[name] for name, total in measured.items()):
        raise ValueError('Attribution must reproduce both rollout endpoints')
    for name, bins in changes.items():
        for label, metric in (('passes', 'holdoutPasses'), ('lookups', 'paidLookups')):
            if sum(point[label] for point in bins.values()) != totals[name][metric] - totals[BOUNDED][metric]:
                raise ValueError('Cycle replacements must telescope exactly')
    return changes


def replay(plan, panels, models, static, gepa, simple, previous):
    screens = options(plan)
    runners = {name: partial(run_qualification_prefix_cycle, screens=tuple(screens[action] for action in table))
               for name, table in plan['actions'].items()}
    runners[ROUTER] = adaptive.routed_runner(plan, models, static)
    schedules = {name: dict.fromkeys(plan['subjects'], name) for name in runners}
    grades = {}
    totals, hashes = adaptive.replay(plan, panels, runners, schedules, grades)
    for name in (BOUNDED, SWITCH, ROUTER):
        if totals[name] != previous['policies'][name] or any(
                trace[name] != previous['trajectoryHashes'][panel][name] for panel, trace in hashes.items()):
            raise ValueError('The existing bounded opening, switch and router paths must reproduce')
    attribution = attribute(plan, panels, runners, totals)
    paired = native.frozen.paired_effects.paired_effect
    controls_at_spend = {}
    for name in (FIT, FIRST, SECOND):
        vectors = {subject: dict(values) for subject, values in grades.items()}
        spend = totals[name]['paidLookups']
        simple_controls = parent.compare_simple(plan, panels, simple, spend, vectors)
        bounds, anchors = parent.compare_native(plan, panels, gepa, spend,
                                                 simple['settingsTotals'][adaptive.RETAIN]['holdoutPasses'], vectors)
        controls_at_spend[name] = {'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors,
                                   'simpleAtBudget': simple_controls,
                                   'paired': {other: paired(vectors, name, other, plan)
                                              for other in (BOUNDED, SWITCH, ROUTER, *simple_controls, *anchors)}}
    return {'episodes': len(panels) * len(plan['seeds']), 'policies': totals, 'trajectoryHashes': hashes,
            'replacements': attribution, 'comparisons': controls_at_spend}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, prior, previous_fit = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, inputs = target(args.cohort, plan, prior, previous_fit, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        groups, _, _ = discovery.training(prior[2])
        report = fit(plan, previous_fit, groups)
    else:
        report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
