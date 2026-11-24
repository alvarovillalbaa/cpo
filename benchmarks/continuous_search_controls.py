"""Compare fixed-roster search controls on the sealed three-cycle archives."""

import argparse
from collections import Counter
from functools import partial
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import continuous_archive_routing as continuous
from benchmarks import promotion_aware_archive_routing as promotion
from cpo._contract import digest
from cpo.single_finalist import FinalistResult
from cpo.two_sided_certificate_cycle import _run


native, transfer = continuous.native, continuous.transfer
PRIMARY, STATIC, RETAIN = continuous.PRIMARY, continuous.STATIC, continuous.RETAIN
HALVING, UNIFORM = 'successive-halving', 'uniform'
MODES = (HALVING, UNIFORM)
WIDTHS = (4, 8)
RUNGS = (1, 2, 4)


def settings(rows):
    """Enumerate every feasible completed-round prefix at each width."""
    for mode in MODES:
        for width in WIDTHS:
            active, price = width, 0
            for observed in range(1, rows + 1):
                price += active + 1
                yield f'{mode}/{width}/{max(rows, price)}', mode, width, max(rows, price)
                if mode == HALVING and observed in RUNGS:
                    active = (active + 1) // 2


def screen(incumbent, candidates, rows, evaluate, cap, *, mode, width):
    active = list(candidates[:width])
    order = {prompt: index for index, prompt in enumerate(active)}
    counts = dict.fromkeys((incumbent, *active), 0)
    paid, observed = 0, 0
    for row in rows:
        if not active or paid + len(active) + 1 > cap:
            break
        for prompt in (incumbent, *active):
            counts[prompt] += evaluate(prompt, row).passed
            paid += 1
        observed += 1
        # Stable ties follow the frozen candidate order even after pruning.
        active.sort(key=lambda prompt: (-counts[prompt], order[prompt]))
        if mode == HALVING and observed in RUNGS:
            active = active[:(len(active) + 1) // 2]
    if not active or counts[active[0]] <= counts[incumbent]:
        return FinalistResult(incumbent, None, paid), None
    winner = active[0]
    return FinalistResult(winner, winner, paid), ((counts[incumbent], observed), (counts[winner], observed))


def prepare(cohort):
    base, panels, models, static, _ = continuous.prepare(cohort)
    lock = promotion.RECEIPTS[cohort]
    ref = json.loads(transfer.read_locked(f'docs/continuous-archive-routing-{cohort.lower()}-v1.json', lock))
    if ref['planSha256'] != digest(base):
        raise ValueError('Every comparator must use the exact original three-cycle episodes')
    plan = {**base, 'protocol': 'continuous-search-controls-v1', 'parentReceiptSha256': lock,
            'sourceSha256': {**base['sourceSha256'], Path(__file__).name: sha256(Path(__file__).read_bytes()).hexdigest()},
            'controls': list(settings(base['caseCounts'][1])),
            'scope': 'Replay the frozen routed and static CPO trajectories. Compare uniform scoring and successive '
                     'halving with a stable seeded roster prefix, one complete common row at a time, shared incumbent '
                     'qualification precheck and exact independent promotion. Keep the same setting in all three '
                     'cycles and sweep all complete-row prefixes. Optimize the common and subject-specific controls '
                     'in hindsight under the routed CPO budget. Keep the chosen schedules fixed while resampling.'}
    return plan, panels, models, static, ref['results']


def measure(plan, panels, models, static, reference):
    cpo = promotion.runner_map(models, static)
    runners = {name: partial(_run, screen=partial(screen, mode=mode, width=width))
               for name, mode, width, _ in plan['controls']}
    caps = {name: cap for name, _, _, cap in plan['controls']}
    budget = reference['cpo'][PRIMARY]['paidLookups']
    verify = continuous.routing.verify_qualification
    run = native.paired.cycle.execute_path
    add = native.paired.frontier.transfer.fitted.prior.add_vector
    traces, by_subject, vectors = {}, {}, {}
    original = {name: Counter() for name in (PRIMARY, STATIC)}
    for subject, model, matrix in panels:
        cells, _ = transfer.case_cells(matrix)
        points = by_subject.setdefault(subject, {name: Counter() for name in (*runners, RETAIN)})
        scores = vectors.setdefault(subject, {})
        paths = {name: [] for name in original}
        for seed in plan['seeds']:
            start, cycles = continuous.stages(subject, len(matrix[0]), len(matrix), seed, plan)
            held = cycles[0][2][-1]
            transition = promotion.cached_transitions(cells, cycles, cpo, plan['fullRosterCap'])
            for name in original:
                current, cost, path = promotion.rollout(start, len(cycles), (name, name), transition)
                grades = [cells[current][case] for case in held]
                paths[name].append(path)
                original[name].update(holdoutPasses=sum(grades), paidLookups=cost)
                add(scores.setdefault(name, [0] * len(held)), grades)
            transition.cache_clear()

            grades = [cells[start][case] for case in held]
            points[RETAIN].update(holdoutPasses=sum(grades), paidLookups=0)
            add(scores.setdefault(RETAIN, [0] * len(held)), grades)
            for name, runner in runners.items():
                current, cost = start, 0
                for local_seed, roster, roles in cycles:
                    result, ledger = run(runner, cells, current, roster, roles, local_seed, caps[name], 1)
                    verify(cells, current, roles, result, ledger, 1)
                    current = result.prompt
                    cost += len(ledger)
                grades = [cells[current][case] for case in held]
                points[name].update(holdoutPasses=sum(grades), paidLookups=cost)
                add(scores.setdefault(name, [0] * len(held)), grades)
        panel = f'{subject}/{model}'
        traces[panel] = {name: digest(path) for name, path in paths.items()}
        if any(value != reference['panelTrajectoryHashes'][panel][name] for name, value in traces[panel].items()):
            raise ValueError('The archived routed and static CPO trajectories must reproduce')
    if any(value != reference['cpo'][name][key] for name, metrics in original.items() for key, value in metrics.items()):
        raise ValueError('The archived CPO scores and lookup totals must reproduce')

    totals = {name: Counter() for name in (*runners, RETAIN)}
    for subject, points in by_subject.items():
        for name, point in points.items():
            if sum(vectors[subject][name]) != point['holdoutPasses']:
                raise ValueError('Every alternative must account for its final holdout grades')
            totals[name].update(point)
    common = {mode: native.gepa.best_fixed(totals, [name for name in caps if name.startswith(f'{mode}/')], budget)
              for mode in MODES}
    ceiling = native.gepa.frontier.transfer.fitted.prior.by_subject_ceiling
    tuned = ceiling(by_subject, tuple(runners), {PRIMARY: budget})[PRIMARY]
    schedules = {mode: dict.fromkeys(by_subject, point['setting']) for mode, point in common.items()}
    schedules['subject-tuned'] = tuned['settingsBySubject']
    for name, schedule in schedules.items():
        expected = tuned if name == 'subject-tuned' else common[name]
        if any(sum(by_subject[subject][setting][key] for subject, setting in schedule.items()) != expected[key]
               for key in ('holdoutPasses', 'paidLookups')):
            raise ValueError('Each chosen schedule must attain its reported score and cost')
    # Names in the selected schedules cannot collide with any concrete setting.
    for subject, scores in vectors.items():
        scores.update({name: scores[schedule[subject]] for name, schedule in schedules.items()})
    paired = native.frozen.paired_effects.paired_effect
    effects = {name: paired(vectors, PRIMARY, name, plan) for name in (*schedules, STATIC)}
    gate = (reference['primaryGatePassed'] and all(effects[name]['pairedRange95'][0] > 0 for name in MODES)
            and effects['subject-tuned']['holdoutPassDifference'] > 0)
    return {'cpo': original, 'bestCommon': common, 'subjectTuned': tuned, 'pairedPrimary': effects,
            'settingsTotals': totals, 'settingsBySubject': by_subject, 'cpoTrajectoryHashes': traces,
            'baselineGatePassed': gate}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=continuous.COHORTS, required=True)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, panels, models, static, ref = prepare(args.cohort)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists() or version('gepa') != plan['gepaVersion']:
        parser.error('Replay requires the current seal, a fresh path and pinned GEPA')
    result = measure(plan, panels, models, static, ref)
    with args.out.open('x') as out:
        json.dump({'plan': plan, 'planSha256': seal, 'providerRequests': 0, 'results': result}, out, indent=2,
                  sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
