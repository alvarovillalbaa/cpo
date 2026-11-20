"""Spread first probes across two misses without buying second challenger probes."""

import argparse
from collections import Counter
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import case_difficulty_allocation as parent
from benchmarks import routed_score_allocation as route
from cpo._contract import digest
from cpo.lazy_incumbent import select_with_lazy_incumbent
from cpo.single_finalist import FinalistResult


ROOT = Path(__file__).resolve().parents[1]
AUDIT_REPORT = '794ae33cb08a33ae27f7d6c46a5406d2bc9ef639b77e7ea6cd20a91042d9fde0'
LOOKAHEAD = 2
METHODS = ('alternate-misses', 'shared-probe-with-scan')
CONTROLS = ('strict', *route.GEPA, 'retain-start')


def select(incumbent, candidates, rows, evaluate, *, metric_limit, audit, alternate):
    rows, candidates = tuple(rows), tuple(candidates)
    limit = max(0, metric_limit - (2 * len(rows) - 1))
    if limit < 2 or len(candidates) < 2:
        return select_with_lazy_incumbent(incumbent, candidates, rows, evaluate, metric_limit=metric_limit)
    known = {}

    def observe(prompt, row):
        key = (prompt, row.id)
        if key not in known:
            if len(known) >= metric_limit:
                raise ValueError('The screen must fund the incumbent and a complete finalist')
            reply = evaluate(prompt, row)
            if type(reply.passed) is not bool:
                raise ValueError('Validation requires exact boolean outcomes')
            known[key] = reply
        return known[key]

    first_index = next((i for i, row in enumerate(rows) if not observe(incumbent, row).passed), None)
    if first_index is None:
        return FinalistResult(incumbent, None, len(known))
    first = rows[first_index]
    second = first
    for index, prompt in enumerate(candidates[:limit]):
        witness = second if alternate and index % 2 else first
        if witness != first:
            audit.update(alternateProbes=1)
        if observe(prompt, witness).passed:
            if witness != first:
                audit.update(alternateFinalists=1)
            validation = rows if witness == first else (witness, *(row for row in rows if row != witness))
            result = select_with_lazy_incumbent(incumbent, (prompt,), validation, observe,
                                               metric_limit=metric_limit - index)
            return FinalistResult(result.prompt, result.finalist, len(known))
        if index == 0:
            for row in rows[first_index + 1:first_index + 1 + LOOKAHEAD]:
                audit.update(incumbentLookaheadReads=1)
                if not observe(incumbent, row).passed:
                    second = row
                    audit.update(secondMisses=1)
                    break
    return FinalistResult(incumbent, None, len(known))


def episode(matrix, held, seed, plan, start, *, alternate):
    counters = Counter()

    def bounded(incumbent, candidates, rows, evaluate, *, metric_limit):
        counters.update(deferredScreens=1)
        return select(incumbent, candidates, rows, evaluate, metric_limit=metric_limit,
                      audit=counters, alternate=alternate)

    with patch.object(route.ties.split, 'select_with_lazy_incumbent', bounded):
        costs, trace = route.run(matrix, held, seed, plan, start, 'strict')
    costs.update(counters)
    return costs, trace


def prepare():
    previous, inputs = parent.prepare()
    known = parent.checked_file('docs/affordable-challenger-attribution-results-v1.json', AUDIT_REPORT)
    paths = ('benchmarks/bounded_miss_alternation.py', 'benchmarks/affordable_challenger_attribution.py',
             'benchmarks/routed_witness_split.py', 'cpo/lazy_incumbent.py', 'cpo/challenger.py')
    design = {'protocol': 'cpo-bounded-miss-alternation-v1', 'parentDesignSha256': digest(previous),
              'challengerAuditSha256': AUDIT_REPORT, 'minimumProofReserve': 'Full incumbent and candidate panels',
              'maximumIncumbentLookahead': LOOKAHEAD, 'methods': METHODS, 'primary': METHODS[0], 'controls': CONTROLS,
              'scope': ('After the first challenger fails its inherited witness, discover at most one more '
                        'incumbent miss within two lookups. Alternate cases across subsequent challengers or '
                        'leave the original shared first probe in place. Keep one screen per challenger, '
                        'full proof funding, the original archive, and independent qualification.'),
              'sourceSha256': {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}}
    return design, {name: (*item, known['results'][name]['panels']) for name, item in inputs.items()}


def measure(panels, references, plan, audited):
    labels = (*CONTROLS, *METHODS)
    totals = {key: Counter() for key in labels}
    results, vectors, holdouts = {}, {key: {} for key in METHODS}, {}
    for panel in panels:
        subject, model, matrix = (panel[field] for field in ('subject', 'model', 'correctness'))
        name = f'{subject}/{model}'
        uncertainty = route.CONFIRMATION.uncertainty
        held = route.CONFIRMATION.holdout(subject, len(matrix[0]))
        if holdouts.setdefault(subject, held) != held:
            raise ValueError('Both model splits must share the holdout cases')
        starts = route.ties.costs.retained_prompts(matrix, held, plan['schedule'])
        finals, points = {label: [] for label in labels}, {}
        finals['retain-start'] = starts
        points['retain-start'] = {'holdoutPasses': sum(uncertainty.case_totals(matrix, held, starts).values()),
                                  'paidLookups': 0}
        for label in route.GEPA:
            mode, cap = label.split('/')
            finals[label], points[label] = uncertainty.final_prompts(matrix, held, plan['schedule'], plan, mode, int(cap))

        baseline_losses = {(item['seed'], item['control']): item['furthestStage']
                           for item in audited[name]['losingComparisons']}
        counts, traces = ({label: factory() for label in ('strict', *METHODS)} for factory in (Counter, list))
        for index, (seed, start) in enumerate(zip(plan['schedule']['seeds'], starts, strict=True)):
            original, old_trace = route.run(matrix, held, seed, plan, str(start), 'strict')
            chosen = old_trace[-1]['decision']['selected']
            finals['strict'].append(int(chosen))
            counts['strict'].update(original)
            traces['strict'].append(old_trace)
            baseline = [row['decision']['selected'] for row in old_trace]
            held_controls = {label: sum(matrix[finals[label][index]][case] == '1' for case in held)
                             for label in route.PRIMARY}
            for label in METHODS:
                measured, trace = episode(matrix, held, seed, plan, str(start), alternate=label == METHODS[0])
                selected = [row['decision']['selected'] for row in trace]
                if label == METHODS[1] and selected != baseline:
                    raise ValueError('Buying only incumbent lookahead must preserve every deployment')
                counts[label].update(measured)
                for control in route.PRIMARY:
                    stage = baseline_losses.get((seed, control))
                    if stage and measured['holdoutPasses'] >= held_controls[control]:
                        counts[label][f'recovered/{stage}'] += 1
                counts[label].update(changedFinal=int(selected[-1] != chosen),
                                     improved=int(measured['holdoutPasses'] > original['holdoutPasses']),
                                     regressed=int(measured['holdoutPasses'] < original['holdoutPasses']))
                traces[label].append(trace)
                finals[label].append(int(selected[-1]))

        for label, count in counts.items():
            points[label] = {**count, 'paidLookups': count['searchPaid'] + count['qualificationPaid'],
                             'traceSha256': digest(traces[label])}
        outcomes = {label: uncertainty.case_totals(matrix, held, choices) for label, choices in finals.items()}
        for label, point in points.items():
            if label in CONTROLS and any(key in references[name][label] and point[key] != references[name][label][key]
                                         for key in parent.FIELDS):
                raise ValueError(f'Control changed: {name}/{label}')
            if sum(outcomes[label].values()) != point['holdoutPasses']:
                raise ValueError('Final choices differ from lookup traces')
            totals[label].update({key: value for key, value in point.items() if type(value) is int})
        for label, by_subject in vectors.items():
            margins = by_subject.setdefault(subject, {control: [0] * len(held) for control in CONTROLS})
            for control, values in margins.items():
                for i, case in enumerate(held):
                    values[i] += outcomes[label][case] - outcomes[control][case]
        results[name] = points

    comparisons = {}
    for label, groups in vectors.items():
        ranges = route.transfer.ranges(groups, plan['bootstrap']['draws'], plan['bootstrap']['seed'])
        cost, threshold = totals[label]['paidLookups'], 100 - plan['minimumLookupSavingPercent']
        savings = {ctrl: 1 - cost / totals[ctrl]['paidLookups'] for ctrl in route.GEPA}
        enough = all(100 * cost <= threshold * totals[ctrl]['paidLookups'] for ctrl in route.PRIMARY)
        low, high = ranges['joint']
        gate = 'failed' if not enough or high < 0 else 'passed' if low >= 0 else 'inconclusive'
        comparisons[label] = {'gate': gate, 'lookupSavings': savings, 'caseRanges': ranges}
    return {'totals': totals, 'comparisons': comparisons, 'panels': results}


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
    if any(version('gepa') != plan['gepaVersion'] for _, _, plan, _ in inputs.values()):
        cli.error('Use pinned GEPA 0.1.4')
    results = {name: measure(*data) for name, data in inputs.items()}
    with args.out.open('x') as stream:
        json.dump({'design': design, 'designSha256': seal, 'results': results}, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
