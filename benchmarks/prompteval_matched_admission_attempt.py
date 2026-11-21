"""Give CPO and native GEPA the same option to end after one admission."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_rotating_witness_transfer as transfer
from benchmarks import prompteval_witness_budget_controls as prior
from benchmarks import prompteval_witness_tie_budget as paired
from cpo._contract import digest


REPLAY = transfer.replay
CPO = transfer.CANDIDATE
NATIVE = ('gepa-sequential/52', 'gepa-sequential/60', 'gepa-batched/80', 'gepa-batched/88')
METHODS = (CPO, *NATIVE)
START = 'retain-start'
SNAPSHOT = transfer.ROOT / 'benchmarks/data/qualification-order-transfer-v3.json'
SNAPSHOT_SHA = 'dae40ce166fabd49e8e3559db5a342a4047455c023d32dfe8c0efe2ea80bd326'
REFERENCE = transfer.ROOT / 'docs/prompteval-witness-budget-controls-results-v1.json'
REFERENCE_SHA = '7845ae7d22ad98f4c88c93e4560f3b90d6289da4733d123bdce67e42e0b0c819'


def first(method):
    return f'{method}/one-admission'


def observed_path(matrix, held, start, layouts, active, method, policy, *, verify=False):
    """Capture the first-admission prefix and audit the full episode's paid reads."""
    qualify = REPLAY.qualify
    search_keys = set()
    qualification_reads = 0
    prefix = None

    def search(name, incumbent, layout, observe, limits):
        def track(prompt, case):
            grade = observe(prompt, case)
            search_keys.add((prompt, case))
            return grade

        return transfer.select(name, incumbent, layout, track, limits)

    def admit(incumbent, challenger, *args, **kwargs):
        nonlocal qualification_reads, prefix
        result = qualify(incumbent, challenger, *args, **kwargs)
        selected, _, receipt = result
        qualification_reads += receipt['qualificationLookups']
        if prefix is None and challenger != incumbent:
            prefix = selected, len(search_keys) + qualification_reads
        return result

    with patch.object(REPLAY, 'search', search), patch.object(REPLAY, 'qualify', admit):
        final, full, trace = REPLAY.run_arm(matrix, held, start, layouts, active, method, policy)
    if len(search_keys) + qualification_reads != full['paidLookups']:
        raise ValueError('The path accounting differs from its paid search and admission receipts')
    selected, paid = prefix if prefix is not None else (final, full['paidLookups'])
    if verify:
        attempts = 0

        def limit(name, incumbent, layout, observe, limits):
            nonlocal attempts
            if attempts:
                return incumbent
            nominee = transfer.select(name, incumbent, layout, observe, limits)
            attempts += nominee != incumbent
            return nominee

        with patch.object(REPLAY, 'search', limit):
            capped, counts, _ = REPLAY.run_arm(matrix, held, start, layouts, active, method, policy)
        if (capped, counts['paidLookups']) != (selected, paid):
            raise ValueError('The explicit capped run disagrees with the first-admission prefix')
    return final, full, trace, selected, paid


def prepare():
    source, baseline, data, _, _ = prior.prepare()
    raw = REFERENCE.read_bytes()
    expected = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or expected['planSha256'] != digest(source):
        raise ValueError('The original admission comparison differs from its sealed inputs')
    capture = SNAPSHOT.read_bytes()
    if sha256(capture).hexdigest() != SNAPSHOT_SHA:
        raise ValueError('The bundled BBH and LMentry capture differs from its hash')
    archive = json.loads(capture)['panels']
    seen = {(panel['subject'], panel['model']) for panels in data.values() for panel in panels}
    incoming = {(panel['subject'], panel['model']) for panel in archive}
    if len(incoming) != len(archive) or any({a[field] for a in seen} & {b[field] for b in incoming} for field in (0, 1)):
        raise ValueError('The cross-benchmark subjects and models must be separate from the original panels')
    data = {**data, 'bbh-lmentry-transfer': archive}
    caps = {CPO: baseline['searchCaps'][CPO], **{name: prior.NATIVE[name] for name in NATIVE}}
    plan = {'protocol': 'prompteval-matched-admission-attempt-v1', 'priorPlanSha256': digest(source),
            'priorReceiptSha256': REFERENCE_SHA, 'additionalArchiveSha256': SNAPSHOT_SHA,
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'searchCaps': caps,
            'pairedCaseDraws': source['pairedCaseDraws'], 'resamplingSeed': source['resamplingSeed'],
            'primary': first(CPO), 'controls': [START, *NATIVE, *(first(arm) for arm in NATIVE)],
            'scope': ('Use an identical first-admission rule for each method. The first nominated challenger '
                      'consumes the attempt even when rejected. Count paid reads up to the decision. '
                      'Cross-check the first seed of each panel with explicitly capped runs.')}
    return plan, baseline, data, expected['phases']


def measure(panels, baseline, plan, expected):
    arms = (START, *METHODS, *(first(arm) for arm in METHODS))
    subjects, panels_out = {}, {}
    totals = {arm: Counter() for arm in arms}
    for panel in panels:
        subject, model, matrix = (panel[name] for name in ('subject', 'model', 'correctness'))
        key = f'{subject}/{model}'
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        physical = [panel['caseIDs'][case] for case in held] if 'caseIDs' in panel else held
        group = subjects.setdefault(subject, {'caseIds': physical, 'decisionsPerCase': 0,
                                              'cases': {arm: [0] * len(held) for arm in arms}})
        if len(set(physical)) != len(held) or physical != group['caseIds']:
            raise ValueError('The two model panels must share a physical holdout')
        schedule = baseline['schedule']
        group['decisionsPerCase'] += len(schedule['seeds'])
        counts, traces = {arm: Counter() for arm in arms}, {arm: [] for arm in METHODS}
        for index, seed in enumerate(schedule['seeds']):
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            results = {START: (start, 0)}
            for method, cap in plan['searchCaps'].items():
                active = {**schedule, 'evaluationLookupLimit': cap}
                final, full, trace, selected, paid = observed_path(matrix, held, start, layouts, active, method,
                                                                   baseline['qualificationBank'], verify=index == 0)
                results[method] = final, full['paidLookups']
                results[first(method)] = selected, paid
                traces[method].append((seed, final, trace))
            for arm, (selected, paid) in results.items():
                rows = [matrix[int(selected)][case] == '1' for case in held]
                counts[arm].update(holdoutPasses=sum(rows), paidLookups=paid)
                group['cases'][arm] = [a + b for a, b in zip(group['cases'][arm], rows, strict=True)]
        if expected is not None:
            saved = expected['panels'][key]
            for arm in (*METHODS, first(CPO)):
                old = saved['admission-attempts/1' if arm == first(CPO) else arm]
                if counts[arm] != {name: old[name] for name in ('holdoutPasses', 'paidLookups')}:
                    raise ValueError('A matched source panel changed its score or paid reads')
                if arm in traces and digest(traces[arm]) != old['traceSha256']:
                    raise ValueError('The full native or CPO trace changed')
        for arm in arms:
            totals[arm].update(counts[arm])
        panels_out[key] = {arm: {**counts[arm], **({'fullTraceSha256': digest(traces[arm])} if arm in traces else {})}
                           for arm in arms}
    accuracy = {arm: str(sum(Fraction(sum(group['cases'][arm]), len(group['caseIds']) * group['decisionsPerCase'])
                             for group in subjects.values()) / len(subjects)) for arm in arms}
    return {'totals': totals, 'macroAccuracy': accuracy, 'panels': panels_out,
            'distinctHoldoutCases': sum(len(group['caseIds']) for group in subjects.values())}, subjects


def compare(results, subjects, arm, plan):
    candidate = plan['primary']
    accuracy, costs = results['macroAccuracy'], results['totals']
    paired_panels = {name: {**unit, 'cases': {paired.BASELINE: unit['cases'][arm], candidate: unit['cases'][candidate]}}
                     for name, unit in subjects.items()}
    return {'control': arm, 'accuracyDelta': str(Fraction(accuracy[candidate]) - Fraction(accuracy[arm])),
            'costDelta': costs[candidate]['paidLookups'] - costs[arm]['paidLookups'],
            'pairedRanges': paired.paired_ranges(paired_panels, candidate, plan)}


def execute(plan, baseline, data, reference):
    if version('gepa') != baseline['gepaVersion']:
        raise ValueError('Use the pinned GEPA 0.1.4 package')
    module = import_module('gepa.optimize_anything')
    original = module.optimize_anything

    def split_safe(*args, dataset, valset, **settings):
        train, validation = [transfer.CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('The native search case IDs overlap')
        return original(*args, dataset=train, valset=validation, **settings)

    output = {}
    with patch.object(module, 'optimize_anything', split_safe):
        for cohort, panels in data.items():
            results, subjects = measure(panels, baseline, plan, reference.get(cohort))
            costs, accuracy = results['totals'], results['macroAccuracy']
            control = prior.affordable(plan['controls'], costs, accuracy, costs[plan['primary']]['paidLookups'])
            controls = tuple(dict.fromkeys((control, first(NATIVE[0]), first(NATIVE[2]), CPO)))
            output[cohort] = {**results, 'bestAffordableNative': control,
                              'pairedComparisons': {arm: compare(results, subjects, arm, plan) for arm in controls}}
    return {'plan': plan, 'planSha256': digest(plan), 'phases': output, 'newProviderRequests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Use the current design seal and a fresh output path')
    result = execute(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
