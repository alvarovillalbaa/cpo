"""Compare validation-first and qualification-first pricing for a cheap witness."""

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import feedback_rejection_scout as scout
from benchmarks import language_roster_budget_frontier as frontier
from benchmarks import promptolution_settled_episode_headroom as headroom
from benchmarks import promptolution_settled_episode_transfer as transfer
from benchmarks import promptolution_stage_headroom as stages
from benchmarks import settled_episode_api_parity as parity
from benchmarks import settled_episode_refit as refit
from cpo import feedback_episode as feedback, settled_episode as settled
from cpo._contract import digest
from cpo.fixed_pool_cycle import FixedPoolCycleResult
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


STAGE_SHA = 'b21c445642d67bf4b0196eee706256bdbc9198775f020757006a9d1051e093a1'
VALIDATION_FIRST, QUALIFICATION_FIRST = 'validation-first', 'qualification-first'
ORDERS = (VALIDATION_FIRST, QUALIFICATION_FIRST)
ORIGINAL_DEFERRED = 'packaged-validation-first'
FULL_ROSTER_DEFERRED = 'full-roster-validation-first'
PACKAGED_ORDERS = (ORIGINAL_DEFERRED, FULL_ROSTER_DEFERRED)
ARMS = (*ORDERS, *PACKAGED_ORDERS)
ROSTER_WIDTHS = dict(zip((*settled._ACTIONS[1:], feedback._HALVING), (8, 4, 8), strict=True))


def nominate(incumbent, candidates, rows, evaluate, cap):
    roster = candidates[:4]
    if not roster:
        return FinalistResult(incumbent, None, 0), None
    funded = rows[:min(2, max(0, cap - len(roster)))]

    def read(prompt, row):
        grade = evaluate(prompt, row).passed
        if type(grade) is not bool:
            raise ValueError('Validation requires exact boolean replies')
        return grade

    for opening_cost, row in enumerate(funded, 1):
        if read(incumbent, row):
            continue
        for spent, candidate in enumerate(roster, opening_cost + 1):
            if read(candidate, row):
                return FinalistResult(candidate, candidate, spent), ((0, 1), (1, 1))
        return FinalistResult(incumbent, None, opening_cost + len(roster)), None
    return FinalistResult(incumbent, None, len(funded)), None


def cycle(original, order, incumbent, candidates, validation, qualification, evaluate, *, metric_limit, qualify, seed):
    options = {'metric_limit': metric_limit, 'qualify': qualify, 'seed': seed}
    args = incumbent, candidates, validation, qualification, evaluate
    if any(row.critical for row in validation):
        return original(*args, **options)
    if order == QUALIFICATION_FIRST:
        return _run(*args, **options, screen=nominate)
    return defer_precheck(nominate, *args, **options)


def defer_precheck(screen, incumbent, candidates, validation, qualification, evaluate, *, metric_limit, qualify, seed):
    selection, counts = screen(incumbent, candidates, validation, evaluate, metric_limit)
    if selection.finalist is None:
        return FixedPoolCycleResult(selection, None)
    result = _run(incumbent, candidates, validation, qualification, evaluate, metric_limit=metric_limit,
                  qualify=qualify, seed=seed, screen=lambda *_: (selection, counts))
    # A perfect qualification incumbent can still close the gate before it
    # accepts the nomination. Retain the validation charges in that case.
    return replace(result, search=replace(result.search, evaluations=selection.evaluations))


def defer_packaged(original, incumbent, candidates, validation, qualification, evaluate, *, minimum_width=0, **options):
    args = incumbent, candidates, validation, qualification, evaluate
    if len(candidates) < minimum_width or any(row.critical for row in validation):
        return original(*args, **options)
    return defer_precheck(original.keywords['screen'], *args, **options)


@contextmanager
def use_order(order):
    routes = (settled._RUNNERS, feedback._FEEDBACK_RUNNERS)
    if order in PACKAGED_ORDERS:
        replacements = [{name: partial(defer_packaged, runner,
                                       minimum_width=ROSTER_WIDTHS[name] if order == FULL_ROSTER_DEFERRED else 0)
                         for name, runner in route.items() if name in ROSTER_WIDTHS} for route in routes]
    else:
        replacements = [{name: partial(cycle, runner, order) for name, runner in route.items()} for route in routes]
    with patch.dict(routes[0], replacements[0]), patch.dict(routes[1], replacements[1]):
        yield


def prepare():
    stage = transfer.locked('docs/promptolution-stage-headroom-v1.json', STAGE_SHA)
    stage_plan, original, reference = stages.prepare()
    if digest(stage_plan) != stage['planSha256'] or digest(stage['plan']) != stage['planSha256']:
        raise ValueError('The stage headroom plan must reproduce')
    api = transfer.locked('docs/settled-episode-feedback-api-parity-v1.json', scout.API_SHA)
    plan = {'protocol': 'cpo-witness-nomination-cost-v1', 'stageHeadroomSha256': STAGE_SHA,
            'feedbackAPIReceiptSha256': scout.API_SHA, 'languageTransferReceiptSha256': parity.LOCKS,
            'promptolutionCorpusSha256': original['corpusSha256'], 'gepaVersion': original['gepaVersion'],
            'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'arms': ARMS,
            'method': 'Replace each active noncritical screen with the first observed repair of the first '
                      'incumbent miss within two validation cases by up to four challengers. Compare the same '
                      'nomination with the exact qualification precheck before or after search. Preserve '
                      'the strict qualification proof, opening policy, and handling of rejected finalists. '
                      'Also move the precheck after the original uniform and halving screens as an exact '
                      'cost comparison, retaining the precheck-routed fitted opening. Restrict that move '
                      'to rosters filling the quoted screen width in the final exploratory arm.'}
    return plan, api, original, reference


def prompt_replay(original, reference, archive):
    baseline = headroom.capture(original, archive, reference)
    arms = {f'{arm}/{order}': (arm, order) for arm in transfer.RUNNERS for order in ARMS}
    controls = (transfer.BASE, *transfer.WITNESS, *original['controlSettings'])
    native = (transfer.BASE, *original['nativeMethods'])
    outcomes, pooled, tasks = [], [], {}

    def compare(data, menus):
        return {name: {'packaged': transfer.compare(original, data, name, (arm,), enforce_cap=False),
                       'bestAffordableNativeOrRetain': transfer.compare(original, data, name, native),
                       'allControls': headroom.evaluate(menus, name, controls, None),
                       'nativeHindsight': headroom.evaluate(menus, name, native, None)}
                for name, (arm, _) in arms.items()}

    for task, menus in baseline.items():
        panel = archive[task]
        matrix = panel['correctness']
        held = sorted(Random(f"{original['holdoutSeed']}/{task}").sample(
            range(len(panel['caseIDs'])), transfer.donor.HOLDOUT,
        ))
        totals = {name: Counter() for name in (*menus[0], *arms)}
        vectors = {name: [0] * len(held) for name in totals}
        traces = {name: [] for name in arms}
        for seed, menu in zip(original['seeds'], menus, strict=True):
            windows = transfer.layout(original, task, seed, held)
            outcomes_by_arm = {}
            for name in totals:
                if name in arms:
                    arm, order = arms[name]
                    with use_order(order):
                        winner, costs, trace = transfer.play(original, matrix, windows, seed, arm)
                    if order in PACKAGED_ORDERS and trace[1] != outcomes_by_arm[arm]:
                        raise ValueError('The original screen must preserve every observed decision')
                    witness_key = arm, 'witness'
                    if order in ORDERS and witness_key in outcomes_by_arm and outcomes_by_arm[witness_key] != trace[1]:
                        raise ValueError('Moving the precheck must preserve the entire decision path')
                    if order in ORDERS:
                        outcomes_by_arm[witness_key] = trace[1]
                    traces[name].append(trace)
                else:
                    winner, costs, trace = transfer.play(original, matrix, windows, seed, name)
                    if name in transfer.RUNNERS:
                        outcomes_by_arm[name] = trace[1]
                grades = [matrix[winner][case] == '1' for case in held]
                totals[name].update(costs, holdoutPasses=sum(grades))
                vectors[name] = [a + b for a, b in zip(vectors[name], grades, strict=True)]
                point = frontier.Point(sum(grades), costs['paidLookups'], (name,))
                if name in menu and point != menu[name]:
                    raise ValueError('Original control score and price must reproduce')
                menu[name] = point
        tasks[task] = {'episodes': len(menus), 'totals': totals, 'traceSha256': {m: digest(t) for m, t in traces.items()},
                       'comparisons': compare([(totals, vectors)], menus)}
        pooled.extend(menus)
        outcomes.append((totals, vectors))
    return {'tasks': tasks, 'pooled': compare(outcomes, pooled)}


def language_cohort(plan, panels, gepa, simple, reference):
    totals = {name: Counter() for name in (transfer.FEEDBACK, *ARMS)}
    traces = {name: sha256() for name in totals}
    changes, vectors, episodes = Counter(), {}, 0
    add = refit.native.paired.frontier.transfer.fitted.prior.add_vector
    effects = refit.native.frozen.paired_effects.paired_effect
    for subject, model, seed, cells, stages, start in refit.previous.episodes(plan, panels):
        observed = {transfer.FEEDBACK: scout.language_episode(cells, stages, start)}
        for order in ARMS:
            with use_order(order):
                observed[order] = scout.language_episode(cells, stages, start)
        for tested, baseline in ((VALIDATION_FIRST, QUALIFICATION_FIRST),
                                  *((order, transfer.FEEDBACK) for order in PACKAGED_ORDERS)):
            first, second = observed[tested][0], observed[baseline][0]
            if (first.cycle_schedules != second.cycle_schedules or
                    [(step.search.finalist, step.prompt) for step in first.cycles] !=
                    [(step.search.finalist, step.prompt) for step in second.cycles]):
                raise ValueError('Precheck ordering changed an observed decision')
            changes.update({f'{tested}Cheaper': int(first.evaluations < second.evaluations),
                            f'{tested}Costlier': int(second.evaluations < first.evaluations)})
        for name, (result, paid) in observed.items():
            grades = [cells[result.prompt][case] for case in stages[0][2][-1]]
            add(vectors.setdefault(subject, {}).setdefault(name, [0] * len(grades)), grades)
            totals[name].update(holdoutPasses=sum(grades), paidLookups=len(paid),
                                overriddenCycles=sum(action != result.schedule for action in result.cycle_schedules))
            totals[name].update(f'{role}Lookups' for role, *_ in paid)
            traces[name].update(bytes.fromhex(digest((subject, model, seed, result.prompt, result.cycle_schedules, paid))))
        episodes += 1
    hashes = {name: trace.hexdigest() for name, trace in traces.items()}
    baseline = totals[transfer.FEEDBACK]
    if (episodes != reference['episodes'] or hashes[transfer.FEEDBACK] != reference['paidTraceSha256']
            or {key: baseline[key] for key in reference['totals']} != reference['totals']):
        raise ValueError('Verify packaged feedback before comparing lookup costs')
    comparisons = {}
    for name in ARMS:
        peers = {subject: dict(scores) for subject, scores in vectors.items()}
        bounds, anchors = refit.parent.compare_native(
            plan, panels, gepa, totals[name]['paidLookups'], simple['settingsTotals'][refit.RETAIN]['holdoutPasses'], peers,
        )
        comparisons[name] = {'nativeBoundsAtCost': bounds, 'nativeAnchors': anchors,
                             'paired': {peer: effects(peers, name, peer, plan) for peer in (transfer.FEEDBACK, *anchors)}}
    return {'episodes': episodes, 'totals': totals, 'traceSha256': hashes, 'comparisons': comparisons, 'orderCosts': changes}


def language_replay(api):
    plan, context, baseline = refit.contract()
    frozen = json.loads(refit.transfer.read_locked('docs/settled-episode-refit-v1.json', parity.FIT_SHA))
    results = {}
    for cohort in refit.discovery.COHORTS:
        target, (panels, _, _, gepa, simple, _) = refit.target(cohort, plan, context, baseline, frozen)
        archived = transfer.locked(f'docs/settled-episode-refit-transfer-{cohort.lower()}-v1.json', parity.LOCKS[cohort.lower()])
        if digest(target) != archived['planSha256'] or digest(archived['plan']) != archived['planSha256']:
            raise ValueError('Use the original target layout')
        results[cohort] = language_cohort(target, panels, gepa, simple, api['cohorts'][cohort])
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, api, original, reference = prepare()
    seal = digest(plan)
    if not (args.corpus or args.execute or args.out):
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if not args.corpus or args.execute != seal or not args.out or args.out.exists():
        parser.error('Replay requires the pinned corpus, current seal, and a fresh output')
    if version('gepa') != plan['gepaVersion']:
        parser.error('Use the pinned GEPA environment')
    archive = transfer.donor.load_corpus(args.corpus.read_bytes())
    report = {'plan': plan, 'planSha256': seal, 'providerRequests': 0,
              'promptolution': prompt_replay(original, reference, archive), 'language': language_replay(api)}
    with args.out.open('x') as stream:
        stream.write(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
