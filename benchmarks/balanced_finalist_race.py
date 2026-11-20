"""Compare matched-case finalist races against the archived GEPA winners."""

import argparse
from collections import Counter
from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import archive_complementarity_transfer as archive
from benchmarks import budgeted_second_probe as probes
from benchmarks import four_case_qualification_transfer as mmlu
from benchmarks import independent_mmlu_cost_frontier as frontier
from benchmarks import qualification_role_transfer as roles
from benchmarks import tie_extension_cross_benchmark as cross
from benchmarks.independent_mmlu_transfer import read_json
from benchmarks.prompteval_transfer import holdout
from cpo import fixed_pool_cycle, select_pool
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
PHASES = ('bbh-lmentry', 'mmlu')
RACES = {'balanced-four': (4, 4), 'balanced-six': (6, 2)}
ROUTED = ('wide-at-start', 'wide-after-two-misses')
METHODS = ('seeded', 'certified-halving', 'recheck-first-failures', 'ordered-exact', *RACES, *ROUTED)
SOURCE_SHA256 = 'f6c4d253794d3d6279929e15663a9d25c166d88d5f96a021f57886317a2b24a8'
SCORES = ('holdoutPasses', 'paidLookups')


def matched_prefix(rows, incumbent, count):
    """Use equally many incumbent misses and passes when both are available."""
    half = count // 2
    misses = [row for row in rows if not incumbent[row.id]]
    passes = [row for row in rows if incumbent[row.id]]
    first = misses[:half] + passes[:half]
    remainder = [row for row in rows if row not in first]
    return first + remainder


def balanced_screen(incumbent, candidates, rows, evaluate, *, metric_limit, width, screen_rows):
    rows, candidates = tuple(rows), tuple(candidates)[:width]
    finalists = min(2, len(candidates))
    reserve = len(rows) + len(candidates) * screen_rows + finalists * (len(rows) - screen_rows)
    if metric_limit < reserve or not 0 < screen_rows <= len(rows):
        raise ValueError('The selected roster and two finalist proofs must fit the search cap')
    if not candidates:
        return FinalistResult(incumbent, None, 0)
    baseline = {row.id: evaluate(incumbent, row) for row in rows}
    order = matched_prefix(rows, {key: reply.passed for key, reply in baseline.items()}, screen_rows)

    def measure(prompt, row):
        return baseline[row.id] if prompt == incumbent else evaluate(prompt, row)

    result = select_pool((incumbent, *candidates), order, measure, metric_limit=metric_limit, screen_rows=screen_rows,
                         max_challenges=finalists, adaptive_rejection=True)
    return FinalistResult(result.prompt, result.prompt if result.prompt != incumbent else None, result.evaluations)


def run(matrix, held, seed, plan, method):
    original = plan['schedule']
    if method in probes.METHODS:
        return probes.run_episode(matrix, held, seed, original, plan, method)
    start, _ = archive.continuous.schedule(len(matrix[0]), len(matrix), held, seed, original)
    routing = Counter(wideCycles=0)

    def screen(incumbent, candidates, rows, evaluate, *, metric_limit):
        if method in ROUTED:
            rows = tuple(rows)
            known = {}

            def observe(prompt, row):
                key = prompt, row.id
                if key not in known:
                    if len(known) == metric_limit:
                        raise ValueError('The routed race exceeded its search ceiling')
                    known[key] = evaluate(prompt, row)
                return known[key]

            widen = incumbent == start if method == 'wide-at-start' else all(
                not observe(incumbent, row).passed for row in rows[:2])
            routing.update(wideCycles=int(widen))
            if widen:
                result = balanced_screen(incumbent, candidates, rows, observe, metric_limit=metric_limit,
                                         width=6, screen_rows=2)
            else:
                result = fixed_pool_cycle.select_with_lazy_incumbent(
                    incumbent, candidates, rows, observe, metric_limit=metric_limit)
            return replace(result, evaluations=len(known))
        if method in RACES:
            width, size = RACES[method]
            return balanced_screen(incumbent, candidates, rows, evaluate, metric_limit=metric_limit,
                                   width=width, screen_rows=size)
        result = select_pool((incumbent, *candidates), rows, evaluate, metric_limit=metric_limit, adaptive_rejection=True)
        return FinalistResult(result.prompt, result.prompt if result.prompt != incumbent else None, result.evaluations)

    def cycle(*args, **kwargs):
        return fixed_pool_cycle.run_fixed_pool_cycle(*args, screen=method, **kwargs)

    with patch.dict(fixed_pool_cycle._SCREENS, {method: screen}), patch.object(archive, 'run_fixed_pool_cycle', cycle):
        totals, trace = archive.episode(matrix, held, seed, original, plan, 'recency')
    totals.update(routing)
    return totals, trace


def prepare(phase):
    if phase == 'bbh-lmentry':
        parent, label, controls = cross.design(), 'tie-extension-cross-benchmark', ('gepa-batched-eight', 'gepa-sequential-eight')
        baseline, expected = 'cpo-eight', SOURCE_SHA256
    else:
        parent, label, controls = mmlu.design(), 'four-case-qualification-transfer', ('gepa-batched-eight-52', 'gepa-sequential-eight-52')
        baseline, expected = 'cpo-eight-52', roles.TRANSFER_SHA256
    base = (ROOT / 'docs' / f'{label}-results-v1.json').read_bytes()
    corpus = (ROOT / 'benchmarks/data' / f'{label}-v1.json').read_bytes()
    reference = read_json(base)
    if (sha256(base).hexdigest() != expected or reference['planSha256'] != digest(parent)
            or reference['corpusSha256'] != sha256(corpus).hexdigest()):
        raise ValueError('The archived baseline or source corpus differs')
    plan = {
        'protocol': 'cpo-balanced-finalist-race-v1', 'phase': phase, 'parentPlanSha256': digest(parent),
        'sourceReportSha256': expected, 'corpusSha256': reference['corpusSha256'], 'methods': list(METHODS),
        'races': {key: {'rosterWidth': width, 'screenRows': rows, 'maximumFinalists': 2}
                  for key, (width, rows) in RACES.items()},
        'routedRaces': {'wide-at-start': 'Use balanced-six when the initial prompt is incumbent.',
                        'wide-after-two-misses': 'Use balanced-six when the incumbent fails the first two cases.'},
        'schedule': parent['schedule'], 'validationRows': parent['validationRows'], 'searchCap': 52,
        'gepaVersion': parent['gepaVersion'],
        'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in (
            'benchmarks/balanced_finalist_race.py', 'benchmarks/budgeted_second_probe.py',
            'benchmarks/qualification_role_transfer.py', 'benchmarks/gepa_paid_cap_transfer.py',
            'benchmarks/archive_complementarity_transfer.py', 'cpo/pool.py')},
        'scope': ('Shortlist the top two on shared incumbent-pass and incumbent-miss cases, then score '
                  'both finalists exactly when they can beat the leader. Keep the archive and eight-case gate. '
                  'Compare previously observed cohorts and replay both official GEPA controls at cap 52.'),
    }
    refs = {name: dict(zip(('seeded', 'gepaBatched', 'gepaSequential'),
                           [panel['methods'][key] for key in (baseline, *controls)], strict=True))
            for name, panel in reference['panels'].items()}
    return plan, read_json(corpus)['panels'], refs


def panel_results(matrix, held, plan, refs):
    original = plan['schedule']
    methods, by_seed, baseline_traces = {}, {}, []
    for method in METHODS:
        totals, trace = Counter(), []
        for seed in original['seeds']:
            counts, journal = run(matrix, held, seed, plan, method)
            totals.update(counts)
            trace.append(journal)
            by_seed.setdefault(method, {})[seed] = counts['holdoutPasses']
        point = dict(totals, paidLookups=totals['searchPaid'] + totals['qualificationPaid'], traceSha256=digest(trace))
        if method == 'seeded':
            frontier.expect_reference(point, refs[method])
            baseline_traces = trace
        methods[method] = point
    losses = roles.audit_gepa_losses(matrix, held, original, plan, baseline_traces, refs)
    eligible = [row for row in losses if row['reason'] == 'strict-gain-winner-missed-by-screen']
    for method in METHODS:
        methods[method]['ScreenMissLossesMatchedOrExceeded'] = sum(
            by_seed[method][row['seed']] >= by_seed['seeded'][row['seed']] + row['passDeficit'] for row in eligible)
    for label in ('gepaBatched', 'gepaSequential'):
        methods[label] = {key: refs[label][key] for key in SCORES}
    return {'methods': methods, 'seededLosses': losses}


def replay(plan, panels, reference):
    results, totals, attribution = {}, {}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = holdout(subject, len(matrix[0]))
        results[name] = panel_results(matrix, held, plan, reference[name])
        for mode, point in results[name]['methods'].items():
            keys = (*SCORES, 'ScreenMissLossesMatchedOrExceeded')
            totals.setdefault(mode, Counter()).update({key: point[key] for key in keys if key in point})
        for loss in results[name]['seededLosses']:
            attribution.setdefault(loss['control'], Counter()).update([loss['reason']])
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': results, 'seededLossReasons': attribution}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--phase', choices=PHASES, required=True)
    cli.add_argument('--execute')
    cli.add_argument('--out', type=Path)
    args = cli.parse_args()
    plan, *inputs = prepare(args.phase)
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        cli.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(result, out, sort_keys=True, indent=2)
        out.write('\n')


if __name__ == '__main__':
    main()
