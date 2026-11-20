"""Transfer posterior validation allocation to the archived four-cycle MMLU route."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import recorded_score_allocation as allocation
from benchmarks import routed_training_corroboration as transfer
from benchmarks import routed_validation_ties as ties
from cpo import select_pool
from cpo._contract import digest
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = 'af81c8074ccc492559056dab2550bad034c25ae7e0e82f9b11f4c3114157b72f'
POLICIES = ('exact-wide', 'posterior-wide', 'posterior-all')
METHODS = ('strict', *POLICIES)
PRIMARY = transfer.PRIMARY
LOWER_COST = 'gepa-batched.runner-up/47'
GEPA = (*PRIMARY, LOWER_COST)
CONFIRMATION = ties.confirmation


def select(incumbent, candidates, rows, evaluate, *, metric_limit, posterior):
    rows, candidates = tuple(rows), tuple(candidates)
    ledger = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in ledger:
            if len(ledger) == metric_limit:
                raise ValueError('The alternative race exceeded its evaluation cap')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('The allocation policy needs exact binary replies')
            ledger[key] = reply
        return ledger[key]

    if posterior:
        winner = allocation.allocate(incumbent, candidates, rows, observe, ledger, limit=metric_limit)
    else:
        result = select_pool((incumbent, *candidates), rows, observe, metric_limit=metric_limit, adaptive_rejection=True)
        if result.evaluations != len(ledger):
            raise ValueError('The exact race did not reproduce its search receipt count')
        winner = result.prompt
    return FinalistResult(winner, winner if winner != incumbent else None, len(ledger))


def run(matrix, held, seed, plan, start, method):
    if method == 'strict':
        return ties.run(matrix, held, seed, plan, start, 'strict')
    calls = Counter()

    def wider(incumbent, candidates, rows, evaluate, *, metric_limit, width, screen_rows, mode, audit):
        if screen_rows != 2 or mode != 'try-backup':
            raise ValueError('The routed allocator requires the frozen wider-search entry point')
        chosen = select(incumbent, tuple(candidates)[:width], rows, evaluate, metric_limit=metric_limit,
                        posterior=method == 'posterior-wide')
        audit.update(replacedWideScreens=1, wideNominations=int(chosen.prompt != incumbent))
        return chosen

    def every(incumbent, candidates, rows, evaluate, *, metric_limit, **kwargs):
        result = select(incumbent, candidates, rows, evaluate, metric_limit=metric_limit, posterior=True)
        calls.update(replacedFreshSearches=1, freshNominations=int(result.prompt != incumbent))
        return result

    target, name, selector = ((ties.split, 'routed_selection', every) if method == 'posterior-all' else
                              (ties.split.balanced, 'screen', wider))
    with patch.object(target, name, selector):
        totals, trace = ties.run(matrix, held, seed, plan, start, 'strict')
    totals.update(calls)
    return totals, trace


def prepare():
    parent, panels, strict, comparisons = transfer.prepare()
    raw = (ROOT / 'docs/recorded-score-allocation-results-v1.json').read_bytes()
    math_plan, _ = allocation.prepare()
    if sha256(raw).hexdigest() != SOURCE_SHA256 or json.loads(raw)['planSha256'] != digest(math_plan):
        raise ValueError('The posterior allocator does not reproduce its recorded source comparison')
    paths = ('benchmarks/routed_score_allocation.py', 'benchmarks/recorded_score_allocation.py',
             'benchmarks/finalist_screen_budget.py', 'cpo/pool.py', *parent['sourceSha256'])
    plan = {**{k: parent[k] for k in ('schedule', 'validationRows', 'searchCap', 'gepaVersion',
                                     'bootstrap', 'minimumLookupSavingPercent')},
            'protocol': 'cpo-routed-score-allocation-v1', 'methods': METHODS, 'primary': 'posterior-wide',
            'primaryControls': PRIMARY, 'cheaperControl': LOWER_COST, 'parentPlanSha256': digest(parent),
            'scoreAllocationPlanSha256': digest(math_plan), 'scoreAllocationReportSha256': SOURCE_SHA256,
            'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths},
            'scope': ('Replace the original six-candidate wider screen with an exact or posterior race. '
                      'Also apply posterior allocation to every fresh search as a separate policy. '
                      'Keep all starts, paid budgets, archive policy and independent qualification fixed.')}
    return plan, panels, strict, comparisons


def replay(plan, panels, strict, references):
    totals = {m: Counter() for m in (*METHODS, *GEPA, 'retain-start')}
    results, subjects, holdouts = {}, {m: {} for m in POLICIES}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        held = CONFIRMATION.holdout(subject, len(matrix[0]))
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both model panels must share the same holdout case IDs and order')
        starts = ties.costs.retained_prompts(matrix, held, plan['schedule'])
        counts, logs, finals = ({m: factory() for m in METHODS} for factory in (Counter, list, list))
        changes = {m: Counter() for m in POLICIES}
        for seed, start in zip(plan['schedule']['seeds'], starts, strict=True):
            for method in METHODS:
                count, log = run(matrix, held, seed, plan, str(start), method)
                counts[method].update(count)
                logs[method].append(log)
                finals[method].append(int(log[-1]['decision']['selected']))
                if method != 'strict':
                    strict_prompt = finals['strict'][-1]
                    changes[method].update(episodesWithDifferentFinal=int(finals[method][-1] != strict_prompt))
        points = {m: {**count, **changes.get(m, {}), 'paidLookups': count['searchPaid'] + count['qualificationPaid'],
                      'traceSha256': digest(logs[m])} for m, count in counts.items()}
        ties.frontier.expect_reference(points['strict'], strict[name])
        for label in GEPA:
            mode, cap = label.split('/')
            finals[label], points[label] = CONFIRMATION.uncertainty.final_prompts(
                matrix, held, plan['schedule'], plan, mode, int(cap))
            ties.frontier.expect_reference(points[label], references[name][label])
        finals['retain-start'] = starts
        outcomes = {m: CONFIRMATION.uncertainty.case_totals(matrix, held, prompts) for m, prompts in finals.items()}
        points['retain-start'] = {'holdoutPasses': sum(outcomes['retain-start'].values()), 'paidLookups': 0}
        for method, point in points.items():
            if sum(outcomes[method].values()) != point['holdoutPasses']:
                raise ValueError('The archived final-prompt vectors differ from recorded holdout totals')
            totals[method].update({k: v for k, v in point.items() if type(v) is int})
        for candidate, groups in subjects.items():
            vectors = groups.setdefault(subject, {m: [0] * len(held) for m in points if m != candidate})
            for method, vector in vectors.items():
                for pos, case in enumerate(held):
                    vector[pos] += outcomes[candidate][case] - outcomes[method][case]
        results[name] = points

    comparisons = {}
    for candidate, groups in subjects.items():
        budget = totals[candidate]['paidLookups']
        paired = transfer.ranges(groups, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        savings = {m: 1 - budget / totals[m]['paidLookups'] for m in GEPA}
        ceiling = 100 - plan['minimumLookupSavingPercent']
        saves_enough = all(100 * budget <= ceiling * totals[m]['paidLookups'] for m in PRIMARY)
        lower, upper = paired['joint']
        gate = 'failed' if not saves_enough or upper < 0 else 'passed' if lower >= 0 else 'inconclusive'
        comparisons[candidate] = {'caseSensitivityRanges': paired, 'lookupSavingFractions': savings, 'gate': gate}
    return {'plan': plan, 'planSha256': digest(plan), 'panels': results, 'totals': totals, 'comparisons': comparisons}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, sort_keys=True, indent=2))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Execution requires the current seal and a fresh output path')
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use the pinned GEPA version')
    result = replay(plan, *inputs)
    with args.out.open('x') as stream:
        json.dump(result, stream, sort_keys=True, separators=(',', ':'))
        stream.write('\n')


if __name__ == '__main__':
    main()
