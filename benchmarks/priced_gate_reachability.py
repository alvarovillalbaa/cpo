"""Separate prompt-pool headroom from the lookup cost of certifying paths."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import case_difficulty_allocation as parent
from benchmarks import gepa_paid_cap_transfer as gepa
from benchmarks import prompteval_gate_reachability as previous
from benchmarks import routed_score_allocation as route
from cpo._contract import digest


ROOT = Path(__file__).resolve().parents[1]
FRESH_DIRECT = 'full-panel-fresh'
FRESH_MINIMUM = 'minimum-proof-fresh'
ARCHIVE_MINIMUM = 'minimum-proof-archive'
UNCAPPED = 'uncapped-archive'
ANY_OFFERED = 'any-offered'
RETAIN_START = 'retain-start'
MODELS = (FRESH_DIRECT, FRESH_MINIMUM, ARCHIVE_MINIMUM, UNCAPPED)
BOUNDS = (*MODELS, ANY_OFFERED)
CONTROLS = ('strict', *route.PRIMARY)


def update_cost(costs, prompt, cost, budget):
    if cost <= budget and cost < costs.get(prompt, budget + 1):
        costs[prompt] = cost


def paths(matrix, start, layouts, budget):
    """Return cheapest arrivals under each model without reading held-out outcomes."""
    universe = (start, *(prompt for cycle in layouts for prompt in cycle['alternatives']))
    if len(set(universe)) != len(universe):
        raise ValueError('Prompts must be offered once in the archived schedule')
    costs = {mode: {start: 0} for mode in MODELS}
    unconstrained_budget = sum(2 * (len(cycle['validation']) + len(cycle['qualify'])) for cycle in layouts)
    earlier, previous_validation = [start], set()
    for cycle in layouts:
        fresh, validation, qualification = (cycle[key] for key in ('alternatives', 'validation', 'qualify'))
        validation_scores = previous.row_scores(matrix, universe, validation)
        qualification_scores = previous.row_scores(matrix, universe, qualification)
        midpoint = len(qualification) // 2
        first_half = previous.row_scores(matrix, universe, qualification[:midpoint])
        second_half = {prompt: qualification_scores[prompt] - first_half[prompt] for prompt in universe}
        overlap = previous_validation.intersection(validation)
        reused = previous.row_scores(matrix, universe, overlap)

        for mode, arrivals in costs.items():
            reachable = arrivals.copy()
            cap = unconstrained_budget if mode == UNCAPPED else budget
            offers = (*fresh, *earlier) if mode in (ARCHIVE_MINIMUM, UNCAPPED) else fresh
            for incumbent, spent in arrivals.items():
                minimum_search = len(validation) + 1 - (len(overlap) - reused[incumbent])
                for prompt in offers:
                    if qualification_scores[prompt] <= qualification_scores[incumbent]:
                        continue
                    if incumbent == start and (first_half[prompt] < first_half[start]
                                               or second_half[prompt] < second_half[start]):
                        continue
                    archive_move = prompt in earlier
                    if not archive_move and validation_scores[prompt] <= validation_scores[incumbent]:
                        continue
                    if mode == FRESH_DIRECT:
                        charge = 2 * (len(validation) + len(qualification))
                    else:
                        charge = len(qualification) + 1 + (0 if archive_move else minimum_search)
                    update_cost(reachable, prompt, spent + charge, cap)
            costs[mode] = reachable
        earlier.extend(fresh)
        previous_validation.update(validation)
    return {**costs, ANY_OFFERED: dict.fromkeys(universe, 0)}


def prepare():
    design, inputs = parent.prepare()
    sources = ('benchmarks/priced_gate_reachability.py', 'benchmarks/prompteval_gate_reachability.py',
               'benchmarks/prompteval_continuous.py', 'benchmarks/prompteval_validation_size.py',
               'benchmarks/gepa_paid_cap_transfer.py', 'benchmarks/routed_start_protection.py')
    return {'protocol': 'cpo-priced-gate-reachability-v1', 'parentDesignSha256': digest(design),
            'priceLimit': 'Paid search plus qualification of the measured CPO episode, independently for each seed.',
            'qualify': 'Strict exact gain, with nonnegative gain in both halves when leaving the start.',
            'models': BOUNDS, 'controls': CONTROLS, 'earliestMatchingCategories': (RETAIN_START, *BOUNDS),
            'analysis': ('Charge full validation and qualification for a direct fresh path. Price optimistic moves '
                         'using only favorable replies required for an exact binary certificate. Assume earlier '
                         'validation rows are cached for any incumbent and any earlier offer is archived. '
                         'Both path builders skip optional work and use no holdout outcomes until scoring.'),
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in sources}}, inputs


def measure_episode(matrix, held, seed, plan):
    schedule = plan['schedule']
    start, layouts = gepa.smaller.narrow_schedule(
        *gepa.continuous.schedule(len(matrix[0]), len(matrix), held, seed, schedule), plan['validationRows'])
    qualification = {case for cycle in layouts for case in cycle['qualify']}
    search = {case for cycle in layouts for role in ('train', 'validation') for case in cycle[role]}
    if (set(held) & (qualification | search) or qualification & search
            or len(qualification) != sum(len(cycle['qualify']) for cycle in layouts)
            or any(len(set(cycle['validation'])) != len(cycle['validation']) for cycle in layouts)):
        raise ValueError('Search, qualification and holdout must be disjoint')
    if schedule['minimumQualificationGain'] != 1 or any(
            len(layout['qualify']) % 2 or 2 * len(layout['validation']) > plan['searchCap'] for layout in layouts):
        raise ValueError('The bound requires the original scalar paired gate and fundable full validation')

    used, trace = route.run(matrix, held, seed, plan, start, 'strict')
    final = trace[-1]['decision']['selected']
    captures = {'strict': (final, used, trace)}
    for label in route.PRIMARY:
        selected, count, peak, ge_trace = gepa.reinvest_episode(
            matrix, held, seed, schedule, plan, batched=label.startswith('gepa-batched'))
        if peak > plan['searchCap']:
            raise ValueError('GEPA exceeded its archived paid cap')
        captures[label] = selected, count, ge_trace
    budget = used['searchPaid'] + used['qualificationPaid']
    arrivals = paths(matrix, start, layouts, budget)
    if final not in arrivals[ARCHIVE_MINIMUM] or any(
            not arrivals[low].keys() <= arrivals[high].keys() for low, high in zip(BOUNDS, BOUNDS[1:])):
        raise ValueError('The priced bounds failed to contain the measured CPO path or one another')

    held_scores = previous.row_scores(matrix, arrivals[ANY_OFFERED], held)
    if any(held_scores[prompt] != stats['holdoutPasses'] for prompt, stats, _ in captures.values()):
        raise ValueError('A measured control left the sealed pool or has inconsistent holdout totals')
    ceilings = {mode: max(held_scores[prompt] for prompt in arrivals[mode]) for mode in BOUNDS}
    losses, prices, before_final = {}, {}, []
    for control in route.PRIMARY:
        score = captures[control][1]['holdoutPasses']
        if score <= used['holdoutPasses']:
            continue
        losses[control] = RETAIN_START if held_scores[start] >= score else next(
            mode for mode in BOUNDS if ceilings[mode] >= score)
        if any(held_scores[step['decision']['selected']] >= score for step in trace[:-1]):
            before_final.append(control)
        for mode in (FRESH_DIRECT, FRESH_MINIMUM, ARCHIVE_MINIMUM):
            matching = [paid for prompt, paid in arrivals[mode].items() if held_scores[prompt] >= score]
            if matching:
                prices[f'{control}/{mode}'] = min(matching)
    return captures, {'seed': seed, 'cpoPaidLookups': budget, 'ceilings': ceilings, 'firstBound': losses,
                      'matchedWithEarlierDeployment': before_final,
                      'minimumMatchingPrices': prices,
                      'reachableCounts': {mode: len(arrivals[mode]) for mode in BOUNDS}}


def measure(panels, references, plan):
    cohort = {'measured': {arm: Counter() for arm in CONTROLS}, 'holdoutCeilings': Counter(),
              'firstBound': {arm: Counter() for arm in route.PRIMARY}, 'matchedWithEarlierDeployment': Counter(),
              'episodes': 0}
    results = {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        traces, points = {arm: [] for arm in CONTROLS}, {arm: Counter() for arm in CONTROLS}
        ceilings, diagnostics = Counter(), []
        attribution = {arm: Counter() for arm in route.PRIMARY}
        for seed in plan['schedule']['seeds']:
            captures, data = measure_episode(matrix, held, seed, plan)
            for arm, (_, count, trace) in captures.items():
                points[arm].update(holdoutPasses=count['holdoutPasses'],
                                   paidLookups=count['searchPaid'] + count['qualificationPaid'])
                traces[arm].append(trace)
            ceilings.update(data['ceilings'])
            for arm, explanation in data['firstBound'].items():
                attribution[arm].update([explanation])
            cohort['matchedWithEarlierDeployment'].update(data['matchedWithEarlierDeployment'])
            diagnostics.append(data)
        for arm, point in points.items():
            point['traceSha256'] = digest(traces[arm])
            route.ties.frontier.expect_reference(point, references[name][arm])
            cohort['measured'][arm].update({key: point[key] for key in parent.FIELDS[:2]})
        cohort['holdoutCeilings'].update(ceilings)
        for arm, points_by_bound in attribution.items():
            cohort['firstBound'][arm].update(points_by_bound)
        cohort['episodes'] += len(diagnostics)
        results[name] = {'measured': points, 'holdoutCeilings': ceilings, 'firstBound': attribution,
                         'episodes': diagnostics}
    return {'overview': cohort, 'panels': results}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    design, inputs = prepare()
    seal = digest(design)
    if args.execute is None and args.out is None:
        print(json.dumps({'design': design, 'designSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Supply the current seal and a fresh output path')
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan in inputs.values()):
        cli.error('Use the pinned GEPA dependency')
    report = {cohort: measure(*item) for cohort, item in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': report}, stream, sort_keys=True,
                  separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
