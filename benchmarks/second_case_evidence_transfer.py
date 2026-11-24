"""Test whether paid evidence can identify harmful second-case promotions."""

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import second_case_qualification_transfer as previous
from cpo._contract import digest


discovery, depth, parent, native, transfer = previous.discovery, previous.depth, previous.parent, previous.native, previous.transfer
BOUNDED, SWITCH = previous.BOUNDED, previous.SWITCH
KEEP, VETO, SUMMARY, SCRIPT = 'keep-all', 'veto-all', 'paid-summary', 'paid-transcript'
FEATURES = (SUMMARY, SCRIPT)
FIT_SHA = '7b5f9ae8042d58440eef005d9fa8c27c518121611cddb5ecf293f274d5f6e25a'
LOCKS = dict(zip(discovery.COHORTS, (
    '17ef256b4cfd6f7c5c6934aaa34a04ba7b0ec2e2be69e81e05991bee41005e4b',
    'ddd7176b487a0be2d8670274e17e88ff6c1bbeee0190dfeef48c5fe7e0fe11c0',
    '90ad3298e792f7a770f2a7eb11f1ba54ea0b75e31a2637cfde0f164a469d45b4',
    '1094ad498eca54eebe7186963b1d473f6671df6678e7a8fd967485f53b3b13ca',
    'b3d4987a4e0795a462e4b287e072120f499a31b9cf8f2d6a07e7887725f6afd4',
    'e24056365143074416c057cb5cf8553e824131134db694ba740576dcb303d2a8',
    'c815a4ad6cafee5d0a43cc0ce89afaeb17551dd660f937b2bfc0d6c8eb0d67b9',
), strict=True))


@dataclass(frozen=True)
class Opportunity:
    subject: str
    keys: dict
    accepted: tuple
    retained: tuple
    extra_lookups: int

    @property
    def veto_gain(self):
        return sum(self.retained) - sum(self.accepted)


def contract():
    inherited = previous.contract()
    old_plan = inherited[0]
    old_fit = json.loads(transfer.read_locked('docs/second-case-qualification-fit-v1.json', FIT_SHA))
    if digest(old_plan) != old_fit['planSha256'] or digest(old_fit['plan']) != old_fit['planSha256']:
        raise ValueError('The earlier qualification fit must reproduce')
    path = Path(__file__).resolve()
    plan = {**old_plan, 'protocol': 'second-case-evidence-fit-v1', 'previousFitSha256': FIT_SHA,
            'minDiscoverySubjects': 2,
            'sourceSha256': {**old_plan['sourceSha256'], str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest()},
            'scope': 'Allow one veto at the first ordinarily promoted second-case nominee. On both paths '
                     'continue with the fixed switch, with no further veto. Compare freezing a task-blind '
                     'paid-evidence rule on disjoint discovery tasks versus keep-all and veto-all. '
                     'An evidence class needs support from two discovery tasks and positive pooled veto gain. '
                     'Score new-key and conflicting-key coverage before computing hindsight bounds.'}
    return plan, inherited, old_fit


def paid_keys(incumbent, nominee, roster, roles, ledger):
    role_slots = {role: {str(case): i for i, case in enumerate(roles[index])}
                  for role, index in (('validation', 1), ('qualification', 2))}
    prompt_slots = {prompt: index for index, prompt in enumerate(roster)}
    prompt_slots[incumbent] = -1
    trace = [(role, prompt_slots[prompt], role_slots[role][case], grade)
             for (role, prompt, case), grade in ledger.items()]
    qualification = [(ledger.get(('qualification', incumbent, str(case))),
                      ledger.get(('qualification', nominee, str(case)))) for case in roles[2]]
    repairs = sum(pair == (False, True) for pair in qualification)
    losses = sum(pair == (True, False) for pair in qualification)
    lower = sum((base is False) + (draft is True) for base, draft in qualification) - len(qualification)
    return {SUMMARY: digest((repairs, losses, lower)),
            SCRIPT: digest(trace)}


def observations(plan, panels):
    run = native.paired.cycle.execute_path
    trace_point = native.paired.reference.point
    runner = previous.runners(plan)[SWITCH]
    cap = max(value for _, _, _, value in plan['controls'])
    events = []
    baseline, hashes, vectors = Counter(), {}, {}
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        traces = []
        for seed in plan['seeds']:
            start, stages = depth.continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            held = stages[0][2][-1]

            def step(stage, incumbent):
                number, roster, roles = stage
                return run(runner, cells, incumbent, roster, roles, number, cap, 1)

            current, paid, event, trace = start, 0, None, []
            for index, stage in enumerate(stages):
                _, roster, roles = stage
                result, ledger = step(stage, current)
                _, _, signature = trace_point(cells, held, result, ledger)
                trace.append((current, result.prompt, signature))
                paid += len(ledger)
                audit = previous.audit_gate(cells, current, roles, result, ledger, SWITCH)
                if event is None and audit.get('promoted'):
                    keys = paid_keys(current, result.prompt, roster, roles, ledger)
                    exact = [cells[result.prompt][case] - cells[current][case] for case in roles[2]]
                    keys['complete-pairs'] = digest((keys[SCRIPT], exact))
                    event = current, paid, index, keys
                current = result.prompt
            accepted = tuple(cells[current][case] for case in held)
            baseline.update(holdoutPasses=sum(accepted), paidLookups=paid)
            add(vectors.setdefault(subject, [0] * len(held)), accepted)
            traces.append(trace)
            if event is None:
                continue
            retained, counterfactual_cost, index, keys = event
            for suffix in stages[index + 1:]:
                other, ledger = step(suffix, retained)
                counterfactual_cost += len(ledger)
                retained = other.prompt
            alternative = tuple(cells[retained][case] for case in held)
            events.append(Opportunity(subject, keys, accepted, alternative, counterfactual_cost - paid))
        hashes[f'{subject}/{model}'] = digest(traces)
    return baseline, hashes, vectors, events


def groups(events, feature):
    entries = {}
    for event in events:
        entries.setdefault(event.keys[feature], []).append(event)
    return entries


def rule(events, feature, minimum):
    bins = groups(events, feature)
    supported = sorted(key for key, group in bins.items() if len({item.subject for item in group}) >= minimum)
    vetoes = [key for key in supported if sum(event.veto_gain for event in bins[key]) > 0]
    return {'supported': supported, 'vetoes': vetoes}


def apply(method, rules, event):
    return method == VETO or (method in FEATURES and event.keys[method] in rules[method]['vetoes'])


def settlement(baseline, events, method, rules):
    filtered = [event for event in events if apply(method, rules, event)]
    return {'holdoutPasses': baseline['holdoutPasses'] + sum(event.veto_gain for event in filtered),
            'paidLookups': baseline['paidLookups'] + sum(event.extra_lookups for event in filtered),
            'vetoed': len(filtered)}


def ceilings(events, policies):
    result = {'vetoGainWithPerEventHindsight': sum(max(0, event.veto_gain) for event in events),
              'harmfulPromotions': sum(event.veto_gain > 0 for event in events),
              'helpfulPromotions': sum(event.veto_gain < 0 for event in events)}
    for feature in (*FEATURES, 'complete-pairs'):
        bins = groups(events, feature)
        result[feature] = {'classes': len(bins),
                           'mixedSignClasses': sum(any(event.veto_gain > 0 for event in group)
                                                   and any(event.veto_gain < 0 for event in group)
                                                   for group in bins.values()),
                           'vetoGainWithClassHindsight': sum(max(0, sum(event.veto_gain for event in group))
                                                             for group in bins.values()),
                           'byClass': {key: {'vetoGain': sum(event.veto_gain for event in group),
                                            'positive': sum(event.veto_gain > 0 for event in group),
                                            'negative': sum(event.veto_gain < 0 for event in group),
                                            'events': len(group)}
                                       for key, group in bins.items()}}
        if feature in FEATURES:
            support = set(policies[feature]['supported'])
            result[feature]['supportedEvents'] = sum(event.keys[feature] in support for event in events)
    return result


def fit(plan, discovery_groups, prior):
    data = {}
    for cohort, panels in discovery_groups.items():
        eligible = set(map(tuple, plan['fitEnrollment'][cohort]))
        if eligible:
            data[cohort] = observations(plan, [panel for panel in panels if panel[:2] in eligible])
    baseline = {cohort: observed[0] for cohort, observed in data.items()}
    if baseline != prior['byPolicy'][SWITCH]:
        raise ValueError('Every fixed-switch discovery point must reproduce')
    events = [event for _, _, _, group in data.values() for event in group]
    policies = {feature: rule(events, feature, plan['minDiscoverySubjects']) for feature in FEATURES}
    menu = {method: {cohort: settlement(point, group, method, policies)
                     for cohort, (point, _, _, group) in data.items()}
            for method in (KEEP, VETO, *FEATURES)}
    menu[BOUNDED] = prior['byPolicy'][BOUNDED]
    caps = prior['budgets']
    feasible = [arm for arm, totals in menu.items()
                if all(point['paidLookups'] <= caps[cohort] for cohort, point in totals.items())]
    selected = min(feasible, key=lambda arm: (depth.rank(menu[arm]), arm != BOUNDED, arm))
    return {'plan': plan, 'planSha256': digest(plan), 'providerRequests': 0, 'methods': policies, 'selected': selected,
            'eventCount': len(events), 'menu': menu, 'feasible': feasible, 'discoveryCeilings': ceilings(events, policies)}


def target(cohort, plan, inherited, old_fit, fit_receipt):
    if fit_receipt['planSha256'] != digest(plan) or digest(fit_receipt['plan']) != digest(plan):
        raise ValueError('Use the sealed discovery fit')
    old_plan, old_inputs = previous.target(cohort, *inherited, old_fit)
    lock = LOCKS[cohort]
    prior = json.loads(transfer.read_locked(f'docs/second-case-qualification-transfer-{cohort.lower()}-v1.json', lock))
    if prior['planSha256'] != digest(old_plan):
        raise ValueError('The earlier qualification transfer must reproduce')
    target_plan = {**old_plan, 'protocol': 'second-case-evidence-transfer-v1', 'evidenceFitSha256': digest(fit_receipt),
                   'priorTransferSha256': lock, 'evidenceFit': fit_receipt['methods'], 'selectedPolicy': fit_receipt['selected'],
                   'sourceSha256': {**old_plan['sourceSha256'], **plan['sourceSha256']},
                   'scope': 'Measure the first qualified second-case nominee on each fixed-switch trajectory. '
                            'Verify the full accepted path and replay the retain branch. Compare frozen '
                            'task-blind rules at their actual spend. Hindsight ceilings ignore lookup caps '
                            'and apply only to the observed first opportunity on each episode.'}
    panels, _, _, gepa, simple, _ = old_inputs
    return target_plan, (panels, gepa, simple, prior['results'])


def replay(plan, panels, gepa, simple, prior):
    baseline, hashes, grades, events = observations(plan, panels)
    if baseline != prior['policies'][SWITCH] or any(
            signature != prior['trajectoryHashes'][panel][SWITCH] for panel, signature in hashes.items()):
        raise ValueError('The guarded opportunity scan must reproduce every fixed-switch paid path')
    rules = plan['evidenceFit']
    methods = (KEEP, VETO, *FEATURES)
    totals = {method: settlement(baseline, events, method, rules) for method in methods}
    vectors = {subject: {name: list(values) for name in methods} for subject, values in grades.items()}
    for event in events:
        for method in methods:
            if apply(method, rules, event):
                scores = vectors[event.subject][method]
                for index, (accepted, retained) in enumerate(zip(event.accepted, event.retained, strict=True)):
                    scores[index] += retained - accepted
    if any(sum(sum(scores[name]) for scores in vectors.values()) != totals[name]['holdoutPasses'] for name in methods):
        raise ValueError('Paired case scores must reconcile to replay outcomes')
    paired = native.frozen.paired_effects.paired_effect
    comparisons = {}
    for method, point in totals.items():
        spend = point['paidLookups']
        values = {subject: dict(scores) for subject, scores in vectors.items()}
        controls = parent.compare_simple(plan, panels, simple, spend, values)
        bounds, anchors = parent.compare_native(plan, panels, gepa, spend,
                                                 simple['settingsTotals'][previous.adaptive.RETAIN]['holdoutPasses'], values)
        comparisons[method] = {'simpleAtBudget': controls, 'nativeBoundsAtBudget': bounds, 'nativeAnchors': anchors,
                               'paired': {name: paired(values, method, name, plan)
                                          for name in (KEEP, *controls, *anchors) if name != method}}
    return {'episodes': len(panels) * len(plan['seeds']), 'eventCount': len(events), 'fixedSwitchPaidPaths': hashes,
            'policies': {BOUNDED: prior['policies'][BOUNDED], **totals},
            'ceilings': ceilings(events, rules), 'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--fit', action='store_true')
    mode.add_argument('--cohort', choices=discovery.COHORTS)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, inherited, old_fit = contract()
    if args.cohort:
        if args.fitted is None:
            parser.error('Target replay requires a frozen fit')
        plan, inputs = target(args.cohort, plan, inherited, old_fit, json.loads(args.fitted.read_bytes()))
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, pinned GEPA and a fresh output path')
    if args.fit:
        discovery_context = inherited[2]
        training, _, _ = discovery.training(discovery_context[2])
        receipt = fit(plan, training, old_fit)
    else:
        receipt = {'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': replay(plan, *inputs)}
    with args.out.open('x') as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
