"""Fit bounded screen choices on discovery panels and replay them on frozen transfers."""

import argparse
from collections import Counter
from dataclasses import replace
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import shared_validation_archive_transfer as transfer
from cpo import certified_shared_validation_cycle as certified
from cpo._contract import digest
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


STATIC, PREFIX, PROBE = 'fitted-static', 'qualification-prefix', 'prefix-and-validation'
MODELS = (STATIC, PREFIX, PROBE)
BUDGET_CONTROL = 'incumbent-first'
SCREENS = {transfer.RETAIN: None,
           'certified-wide': partial(certified._screen, widths=certified.SCHEDULES['wide'], margin=0),
           BUDGET_CONTROL: transfer.race.previous.incumbent_first_screen,
           'single-repair': partial(transfer.repair_screen, repairs=1),
           'preserve-one': partial(transfer.race.paired_repair_screen, miss_limit=1)}
TRANSFER_LOCKS = dict(zip(transfer.COHORTS, (
    '93466c31c6e2e3167ff02d6e1c6143ac42908535eed2f04150abb3cb37f71966',
    '5949c9fa4b626e41489499db88fd697eea4c5e26d899b2010c7b648da6cd1063',
    'd96aad41bd88bbf76f2006047205a8ffc8bb5d91583e56ba28d155552b1a488d',
    '7a7df5f4faee43f1a3cd0a5f3c4180e808e6b02fffc81d1cd813206c31df3062',
    '659b026abe2476d667a211aa928ef18db8cb08dfd554d9269563322ff1406e9b',
    '0c9ba4c4791e856f52d7f5c4727995a9e4e3c03954a28210240f78a004eb3354',
), strict=True))
METRICS = ('holdoutPasses', 'paidLookups')
BASE_GAIN = 1
OPEN = 'open'
CLOSED = 'closed'


def feature(model, misses_at, first_validation):
    if model == STATIC:
        return OPEN
    if model == PREFIX:
        return str(misses_at)
    return f'{misses_at}/{int(first_validation)}'


def profiled_cycle(incumbent, candidates, validation, qualification, evaluate, *,
                   metric_limit, qualify, minimum_gain, seed, model, choose):
    prefix = []

    def qualify_and_record(prompt, row, repeat):
        grade = qualify(prompt, row, repeat)
        prefix.append(grade)
        return grade

    def route(base, roster, rows, observe, cap):
        if model == PROBE:
            first = observe(base, rows[0])
            if type(first.passed) is not bool:
                raise ValueError('The paid validation feature must be an exact boolean')
        else:
            first = None
        action = choose(feature(model, len(prefix), first.passed if first is not None else None))
        selected = SCREENS[action]
        if selected is None:
            return FinalistResult(base, None, int(first is not None)), None
        if first is None:
            return selected(base, roster, rows, observe, cap)

        paid = 1

        def cached(prompt, row):
            nonlocal paid
            if prompt == base and row.id == rows[0].id:
                return first
            paid += 1
            return observe(prompt, row)

        result, counts = selected(base, roster, rows, cached, cap)
        if paid > cap:
            raise ValueError('The profiled screen must fund the probe within its original search cap')
        return replace(result, evaluations=paid), counts

    return _run(incumbent, candidates, validation, qualification, evaluate, metric_limit=metric_limit,
                qualify=qualify_and_record, minimum_gain=minimum_gain, seed=seed, screen=route)


def training_plan():
    discovery = json.loads(transfer.read_locked(transfer.DISCOVERY, transfer.DISCOVERY_SHA))
    previous = discovery['plan']
    if digest(previous) != discovery['planSha256']:
        raise ValueError('The discovery settings must match their original seal')
    paths = (Path(__file__), Path(transfer.__file__), Path(transfer.race.__file__),
             Path(transfer.race.previous.__file__), Path(transfer.layouts.__file__), Path(certified.__file__),
             transfer.ROOT / 'cpo/two_sided_certificate_cycle.py', transfer.ROOT / 'benchmarks/validation_repair_anchor.py')
    plan = {**{key: previous[key] for key in ('caseCounts', 'challengers', 'seeds', 'fullRosterCap', 'gepaVersion')},
            'protocol': 'paid-prefix-archive-routing-fit-v1', 'discoveryReceiptSha256': transfer.DISCOVERY_SHA,
            'sourceSha256': {str(path.relative_to(transfer.ROOT)): sha256(path.read_bytes()).hexdigest() for path in paths},
            'features': MODELS, 'actions': tuple(SCREENS), 'budgetControl': BUDGET_CONTROL, 'minimumGain': BASE_GAIN,
            'scope': 'Fit one deterministic search choice per observed incumbent qualification-prefix length, '
                     'with or without the first incumbent validation grade. All policies share the original '
                     'independent precheck and proof. Optimize archived held-out passes under the pooled '
                     'incumbent-first budget on discovery alone. Compare with an equally funded fitted static '
                     'choice. Price every physical read and use the fitted static action on unseen states.'}
    return plan, discovery


def replay_point(args, model, choose):
    run = transfer.native.paired.cycle.execute_path
    result, paid = run(partial(profiled_cycle, model=model, choose=choose), *args)
    cells, _, _, (_, _, _, held), _, _, _ = args
    return transfer.native.paired.reference.point(cells, held, result, paid)


def fit(plan, discovery):
    parent, groups, controls, *_ = transfer.native.prepare()
    label = controls[BASE_GAIN]
    if any(digest(parent[key]) != digest(plan[key]) for key in ('caseCounts', 'challengers', 'seeds', 'fullRosterCap')):
        raise ValueError('The frozen layout has changed')
    menus = {model: {} for model in MODELS}
    support = {model: Counter() for model in MODELS}
    closed = Counter()
    native_ceiling = transfer.native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    cap = plan['fullRosterCap']
    fixed_budget = 0
    for cohort, panels in groups.items():
        for subject, model_name, matrix in panels:
            cells, _ = transfer.case_cells(matrix)
            traces = {action: [] for action in ('single-repair', 'preserve-one', BUDGET_CONTROL)}
            for seed in plan['seeds']:
                start, roster, roles = transfer.layouts.schedule(subject, len(matrix[0]), len(matrix), seed, plan)
                args = cells, start, roster, roles, seed, cap, BASE_GAIN
                without_probe = {}
                key = CLOSED
                for action in SCREENS:
                    state = []

                    def choose(observed):
                        state.append(observed)
                        return action

                    point, _, fingerprint = replay_point(args, PREFIX, choose)
                    without_probe[action] = point
                    observed, = state or (CLOSED,)
                    if key != CLOSED and key != observed:
                        raise ValueError('The paid qualification prefix must be independent of the fitted action')
                    key = observed
                    if action in traces:
                        traces[action].append(fingerprint)
                fixed_budget += without_probe[BUDGET_CONTROL]['paidLookups']
                if key == CLOSED:
                    if any(value != without_probe[BUDGET_CONTROL] for value in without_probe.values()):
                        raise ValueError('A closed incumbent precheck must be shared by all choices')
                    closed.update(without_probe[BUDGET_CONTROL])
                    continue
                with_probe = {}
                probe_state = None
                for action in SCREENS:
                    observed_states = []

                    def choose_probe(observed):
                        observed_states.append(observed)
                        return action

                    point, _, _ = replay_point(args, PROBE, choose_probe)
                    observed, = observed_states
                    if probe_state is not None and observed != probe_state:
                        raise ValueError('The paid probe feature must be independent of the fitted action')
                    probe_state = observed
                    with_probe[action] = point
                for mode, state, points in ((STATIC, OPEN, without_probe), (PREFIX, key, without_probe),
                                            (PROBE, probe_state, with_probe)):
                    support[mode][state] += 1
                    menu = menus[mode].setdefault(state, {name: Counter() for name in SCREENS})
                    for action, point in points.items():
                        menu[action].update(point)
            panel = f'{subject}/{model_name}'
            existing = discovery['results'][cohort]['traceHashes'][panel][label]
            if any(digest(path) != existing[action] for action, path in traces.items()):
                raise ValueError('The discovery baselines must reproduce their original lookup paths')

    chosen = {}
    for mode, menu in menus.items():
        budget = fixed_budget - closed['paidLookups']
        best = native_ceiling(menu, tuple(name for name in SCREENS if name != transfer.RETAIN), {mode: budget})[mode]
        actions = best['settingsBySubject']
        point = Counter(closed)
        for state, action in actions.items():
            point.update(menu[state][action])
        if any(point[key] != best[key] + closed[key] for key in METRICS):
            raise ValueError('The fitted policy must reconcile to the training objective')
        chosen[mode] = {'actions': actions, 'trainingPoint': point, 'stateCounts': support[mode]}
    return {'plan': plan, 'planSha256': digest(plan), 'discoveryBudget': fixed_budget,
            'closedPrecheck': closed, 'models': chosen}


def fitted_runner(mode, model, counts):
    fallback = model[STATIC]['actions'][OPEN]

    def choose(state):
        action = model[mode]['actions'].get(state, fallback)
        counts[f'{state}/{action}'] += 1
        return action

    return partial(profiled_cycle, model=mode, choose=choose)


def verify_qualification(cells, start, roles, result, _paid, gain):
    nominee = result.search.finalist
    if nominee is not None:
        exact = sum(cells[nominee][case] - cells[start][case] for case in roles[2])
        if result.prompt != (nominee if exact >= gain else start):
            raise ValueError('Every fitted action must use the original exact independent qualification')


def target_plan(cohort, trained):
    base, groups = transfer.prepare()
    original = json.loads(transfer.read_locked(f'docs/shared-validation-archive-transfer-{cohort.lower()}-v1.json',
                                              TRANSFER_LOCKS[cohort]))
    if original['planSha256'] != digest({**base, 'cohort': cohort}):
        raise ValueError('Use the original frozen transfer layout')
    plan = {**base, 'protocol': 'paid-prefix-archive-routing-transfer-v1', 'cohort': cohort, 'minimumGains': (BASE_GAIN,),
            'fitSha256': digest(trained), 'transferReceiptSha256': TRANSFER_LOCKS[cohort],
            'primaryByCohort': dict.fromkeys(transfer.COHORTS, PROBE),
            'gate': 'The primary routed policy must improve over the fitted static policy at no higher realized '
                    'lookup cost, have a positive paired lower endpoint against the best affordable common GEPA '
                    'setting, and exceed the subject-tuned GEPA ceiling.'}
    return plan, groups[cohort], original['results']


def measure(plan, panels, trained, original):
    mode_counts = {mode: Counter() for mode in MODELS}
    runners = {**transfer.RUNNERS, **{mode: fitted_runner(mode, trained['models'], counter)
                                    for mode, counter in mode_counts.items()}}
    compare = transfer.compare_attainers
    extra = {}

    def compare_with_fitted_static(panels, plan, vectors, schedules, expected, primary):
        paired = transfer.native.frozen.paired_effects.paired_effect
        extra.update({mode: paired(vectors, mode, STATIC, plan) for mode in (PREFIX, PROBE)})
        return compare(panels, plan, vectors, schedules, expected, primary)

    with patch.multiple(transfer, RUNNERS=runners, verify_witness=verify_qualification,
                        compare_attainers=compare_with_fitted_static):
        result = transfer.measure(panels, plan)
    label = f'gain-{BASE_GAIN}'
    for panel, trace in result['panelPathHashes'].items():
        if any(trace[label][action] != original['panelPathHashes'][panel][label][action] for action in transfer.RUNNERS):
            raise ValueError('Every original transfer control path must reproduce')
    if result['nativeSubjectTotalsSha256'] != original['nativeSubjectTotalsSha256']:
        raise ValueError('Every native setting must reproduce before repricing')
    points = result['cpo'][label]
    result['primaryGatePassed'] &= (points[PROBE]['paidLookups'] <= points[STATIC]['paidLookups']
                                    and extra[PROBE]['pairedRange95'][0] > 0)
    return {**result, 'routedActions': mode_counts, 'pairedAgainstFittedStatic': extra}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fit', type=Path)
    parser.add_argument('--fitted', type=Path)
    parser.add_argument('--cohort', choices=transfer.COHORTS)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    freeze, discovery = training_plan()
    if args.fit is not None:
        if any((args.fitted, args.cohort, args.execute, args.out)) or args.fit.exists():
            parser.error('Fitting requires a fresh output path and no transfer arguments')
        trained = fit(freeze, discovery)
        with args.fit.open('x') as out:
            json.dump(trained, out, indent=2, sort_keys=True)
            out.write('\n')
        return
    if args.fitted is None or args.cohort is None:
        parser.error('Transfer requires a frozen fit and cohort')
    trained = json.loads(args.fitted.read_bytes())
    if trained['planSha256'] != digest(freeze) or digest(trained['plan']) != digest(freeze):
        parser.error('Use a fit from the exact frozen discovery plan')
    plan, panels, original = target_plan(args.cohort, trained)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh output path and pinned GEPA')
    report = measure(plan, panels, trained, original)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': report},
                  out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
