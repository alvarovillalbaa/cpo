"""Find retrospective upper bounds on the held-out scores reachable through CPO gates."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from benchmarks import prompteval_continuous as continuous
from benchmarks import prompteval_paid_witness as paid
from benchmarks import prompteval_single_finalist as first
from benchmarks import prompteval_validation_size as smaller
from benchmarks.prompteval_validation_transfer import CPO
from cpo._contract import digest, unique_object


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = '7e995e97a52d68a10fa26a171b7fe61374be6eb291edaf76e8656659fdd3d3b0'
ROUTES = ('strict-fresh', 'strict-with-archive', 'tie-with-archive', 'qualification-only', 'any-offered')


def row_scores(matrix, prompts, cases):
    return {prompt: sum(matrix[int(prompt)][case] == '1' for case in cases) for prompt in prompts}


def reachable_prompts(matrix, initial, layouts):
    """Explore all optimistic paths without consulting the holdout."""
    universe = (initial, *(prompt for layout in layouts for prompt in layout['alternatives']))
    if len(set(universe)) != len(universe):
        raise ValueError('The study assigns each offered prompt to exactly one cycle')
    histories = {route: [{initial}] for route in ROUTES}
    past = {initial}
    for layout in layouts:
        fresh = layout['alternatives']
        validation = row_scores(matrix, universe, layout['validation'])
        qualification = row_scores(matrix, universe, layout['qualify'])
        for route, stages in histories.items():
            current = stages[-1]
            reachable = current.copy()
            if route == 'any-offered':
                reachable.update(fresh)
            else:
                if route != 'strict-fresh':
                    reachable.update(prompt for prompt in past if any(
                        qualification[prompt] > qualification[old] for old in current))
                for prompt in fresh:
                    if any(
                        qualification[prompt] > qualification[old] and (
                            route == 'qualification-only' or validation[prompt] > validation[old] or
                            (route == 'tie-with-archive' and validation[prompt] == validation[old])
                        ) for old in current
                    ):
                        reachable.add(prompt)
            stages.append(reachable)
        past.update(fresh)
    return histories


def compare_episode(matrix, held, initial, layouts, traces):
    reach = reachable_prompts(matrix, initial, layouts)
    if any(step['selected'] not in reachable for step, reachable in zip(
            traces[CPO]['steps'], reach['strict-with-archive'][1:], strict=True)):
        raise ValueError('The measured CPO path fell outside its optimistic bound')
    all_prompts = reach['any-offered'][-1]
    scores = row_scores(matrix, all_prompts, held)
    ceilings = {route: max(scores[p] for p in stages[-1]) for route, stages in reach.items()}
    bounds = [ceilings[route] for route in ROUTES]
    if bounds != sorted(bounds) or scores[traces[CPO]['candidate']] != traces[CPO]['holdoutPasses']:
        raise ValueError('The relaxed routes must contain the tighter routes and preserve recorded scores')
    result = {method: trace['holdoutPasses'] for method, trace in traces.items()}
    if any(trace['candidate'] not in all_prompts or scores[trace['candidate']] != result[method]
           for method, trace in traces.items()):
        raise ValueError('A measured optimizer fell outside the sealed outcome pool')
    attribution = {
        method: next(route for route in ROUTES if ceilings[route] >= result[method])
        for method in first.METHODS[1:] if result[method] > result[CPO]
    }
    return {'measured': result, 'ceilings': ceilings,
            'reachableCounts': {route: len(stages[-1]) for route, stages in reach.items()},
            'firstBoundMatchingGepaOnCpoLoss': attribution}


def prepare(phase):
    raw = (ROOT / 'docs/prompteval-paid-witness-results-v1.json').read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('The archived measured baselines differ')
    previous = json.loads(raw, object_pairs_hook=unique_object)['runs'][phase]['report']
    parent, original, source, _, _ = paid.prepare(phase)
    if digest(parent) != previous['planSha256'] or original['minimumQualificationGain'] != 1:
        raise ValueError('The measured plan or qualification gate differs')
    if tuple(parent['rowsAndCap']) != (12, 52):
        raise ValueError('The report expects the original capped 12-case design')
    plan = {
        'protocol': 'cpo-prompteval-gate-reachability-v1', 'phase': phase,
        'parentPlanSha256': digest(parent), 'parentReportSha256': SOURCE_SHA256,
        'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
        'gepaVersion': parent['gepaVersion'], 'rowsAndCap': parent['rowsAndCap'],
        'freshRoutes': {'strict-fresh': 'validation strict gain and qualification strict gain',
                        'strict-with-archive': 'validation strict gain and qualification strict gain',
                        'tie-with-archive': 'validation tie or gain and qualification strict gain',
                        'qualification-only': 'qualification strict gain', 'any-offered': 'pool membership only'},
        'archiveRelaxation': 'Any previously offered prompt can replace the incumbent on a strict qualification gain.',
        'scope': 'Optimistic retrospective ceilings. The measured arms keep their sealed budget and traces. '
                 'The ceilings omit lookup costs and use holdout only to score full reachable sets.',
    }
    return plan, original, source, previous['panels']


def replay(plan, original, source, published):
    panels = {}
    for panel in source['panels']:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = original['holdoutCaseIDs'][subject]
        trace = []
        measured = {m: [] for m in first.METHODS}
        for seed in original['seeds']:
            episode = first.screened_episode(matrix, held, seed, original, 'first-gain')
            initial, layouts = smaller.narrow_schedule(
                *continuous.schedule(len(matrix[0]), len(matrix), held, seed, original), plan['rowsAndCap'][0])
            if set(held).intersection(case for layout in layouts for role in ('validation', 'qualify')
                                      for case in layout[role]):
                raise ValueError('The holdout must be disjoint from both gate inputs')
            trace.append(compare_episode(matrix, held, initial, layouts, episode))
            for method, series in measured.items():
                series.append(episode[method])
        if (digest(measured[CPO]) != published[name]['baselineFirstGainTraceSha256'] or
                any(first.totals(rows) != published[name]['baseline'][m] for m, rows in measured.items())):
            raise ValueError('The measured references do not reproduce the archived results')
        attribution = {method: dict(Counter(
            row['firstBoundMatchingGepaOnCpoLoss'][method] for row in trace
            if method in row['firstBoundMatchingGepaOnCpoLoss']
        )) for method in first.METHODS[1:]}
        panels[name] = {
            'measured': published[name]['baseline'],
            'oracleHoldoutPasses': {route: sum(row['ceilings'][route] for row in trace) for route in ROUTES},
            'reachablePromptCountSum': {route: sum(row['reachableCounts'][route] for row in trace)
                                        for route in ROUTES},
            'cpoLossAttribution': attribution, 'episodeTraceSha256': digest(trace),
        }
    return {'plan': plan, 'planSha256': digest(plan), 'panels': panels}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=paid.PHASES, required=True)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    report = replay(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
