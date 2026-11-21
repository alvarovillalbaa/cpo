"""Match the retired-admission replay against simpler budget controls."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_retired_admission_witness as retired
from benchmarks import prompteval_rotating_witness_transfer as transfer
from benchmarks import prompteval_witness_tie_budget as paired
from cpo._contract import digest


BASELINE, RETIRED = transfer.CANDIDATE, retired.RETIRED
HISTORICAL = transfer.ROOT / 'docs/prompteval-retired-admission-witness-results-v1.json'
HISTORICAL_SHA = 'd4a43e7f6dbce3c986e055c1ff0d9b2545026cc0a9ce0bf48ccb77beec8c740c'
ADMISSIONS = {f'admission-attempts/{count}': count for count in (1, 2, 3)}
SEARCH = {f'witness-search/{cap}': cap for cap in (16, 24, 32, 40, 48)}
NATIVE = {'retain-start': 0, **{f'gepa-sequential/{cap}': cap for cap in (52, 60, 68, 76, 84, 88)},
          **{f'gepa-batched/{cap}': cap for cap in (80, 82, 84, 86, 88, 96)}}
SIMPLE = ('retain-start', *ADMISSIONS, *SEARCH)


def route(method, incumbent, layout, observe, active, attempts):
    if method in ADMISSIONS:
        if len(attempts) == ADMISSIONS[method]:
            return incumbent
        nominee = transfer.select(BASELINE, incumbent, layout, observe, active)
        if nominee != incumbent:
            attempts.append(nominee)
        return nominee
    return transfer.select(BASELINE if method in SEARCH else method, incumbent, layout, observe, active)


def affordable(methods, totals, accuracy, ceiling):
    return min((arm for arm in methods if totals[arm]['paidLookups'] <= ceiling),
               key=lambda arm: (-Fraction(accuracy[arm]), totals[arm]['paidLookups'], arm))


def prepare():
    upstream, baseline, data, native = retired.prepare()
    raw = HISTORICAL.read_bytes()
    previous = json.loads(raw)
    if sha256(raw).hexdigest() != HISTORICAL_SHA or previous['planSha256'] != digest(upstream):
        raise ValueError('The original retired-admission study does not match its receipt')
    original_panels = paired.evidence.prepare()[4]['panels']
    native = {'prior-transfer': {key: panel['methods'] for key, panel in original_panels.items()},
              'additional-subjects': native['additional-subjects']['panels']}
    source = {'protocol': 'prompteval-witness-budget-controls-v1', 'priorPlanSha256': digest(upstream),
              'priorReceiptSha256': HISTORICAL_SHA, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
              'admissionAttemptCaps': ADMISSIONS, 'witnessSearchCaps': SEARCH, 'nativeSearchCaps': NATIVE,
              'pairedCaseDraws': upstream['pairedCaseDraws'], 'resamplingSeed': upstream['resamplingSeed'],
              'scope': ('Keep original witnesses. End search once the episode has used its admission attempts. '
                        'Charge failed attempts. Compare at realized paid lookups, with all original case splits.'),
              'controlSelection': ('Choose the best affordable fixed simple method on the original subjects, then '
                                   'report that setting on the additional subjects without reselecting it.')}
    return source, baseline, data, previous['phases'], native


def measure(panels, baseline, previous, native):
    old_run = transfer.replay.run_arm
    cap = baseline['searchCaps'][BASELINE]
    caps = {BASELINE: cap, RETIRED: cap, **dict.fromkeys(ADMISSIONS, cap), **SEARCH, **NATIVE}
    totals, subjects, receipts = {arm: Counter() for arm in caps}, {}, {}
    for panel in panels:
        final = {arm: [] for arm in caps}

        def run(matrix, holdout, initial, layouts, active, arm, policy):
            if arm == RETIRED:
                result = retired.history_episode(matrix, holdout, initial, layouts, active, arm)
            else:
                attempts = []

                def choose(method, incumbent, layout, observe, limits):
                    return route(method, incumbent, layout, observe, limits, attempts)

                with patch.object(transfer.replay, 'search', choose):
                    result = old_run(matrix, holdout, initial, layouts, active, arm, policy)
            final[arm].append(int(result[0]))
            return result

        with patch.object(transfer, 'POINTS', caps), patch.object(transfer.replay, 'run_arm', run):
            result = transfer.measure_panel(panel, {**baseline, 'searchCaps': caps})
        subject, model, matrix = (panel[name] for name in ('subject', 'model', 'correctness'))
        key = f'{subject}/{model}'
        methods = result['methods']
        original = {name: value for name, value in previous['panels'][key][BASELINE].items() if name != 'nominations'}
        if methods[BASELINE] != original or methods[RETIRED] != previous['panels'][key][RETIRED]:
            raise ValueError('A sealed CPO control changed its counts or trace')
        for arm in NATIVE.keys() & native[key].keys():
            if methods[arm] != native[key][arm]:
                raise ValueError('A sealed native control changed its counts or trace')
        held = transfer.replay.transfer.holdout(subject, len(matrix[0]))
        group = subjects.setdefault(subject, {'caseIds': held, 'decisionsPerCase': 0,
                                              'cases': {arm: [0] * len(held) for arm in caps}})
        if held != group['caseIds']:
            raise ValueError('A subject must use the same physical held-out cases across models')
        group['decisionsPerCase'] += result['episodeCount']
        for arm in caps:
            outcomes = [sum(matrix[prompt][row] == '1' for prompt in final[arm]) for row in held]
            if len(final[arm]) != result['episodeCount'] or sum(outcomes) != methods[arm]['holdoutPasses']:
                raise ValueError('The selected prompts disagree with the held-out case counts')
            group['cases'][arm] = [first + second for first, second in zip(group['cases'][arm], outcomes, strict=True)]
            totals[arm].update({name: methods[arm][name] for name in ('holdoutPasses', 'paidLookups')})
        receipts[key] = methods
    accuracy = {arm: str(sum(Fraction(sum(group['cases'][arm]), len(group['caseIds']) * group['decisionsPerCase'])
                              for group in subjects.values()) / len(subjects)) for arm in caps}
    return {'totals': totals, 'macroAccuracy': accuracy, 'panels': receipts}, subjects


def compare(subjects, phase, arm, plan):
    # The existing paired resampler accepts the rotating-witness key as its control.
    grouped = {subject: {**rows, 'cases': {RETIRED: rows['cases'][RETIRED], BASELINE: rows['cases'][arm]}}
               for subject, rows in subjects.items()}
    totals, accuracy = phase['totals'], phase['macroAccuracy']
    return {'control': arm, 'retiredMinusControlAccuracy': str(Fraction(accuracy[RETIRED]) - Fraction(accuracy[arm])),
            'retiredMinusControlLookups': totals[RETIRED]['paidLookups'] - totals[arm]['paidLookups'],
            'pairedRanges': paired.paired_ranges(grouped, RETIRED, plan)}


def execute(plan, baseline, data, previous, native):
    if version('gepa') != baseline['gepaVersion']:
        raise ValueError('Use pinned GEPA 0.1.4')
    module = import_module('gepa.optimize_anything')
    original = module.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        train, validation = [transfer.CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('The native control received overlapping train and validation IDs')
        return original(*args, dataset=train, valset=validation, **settings)

    with patch.object(module, 'optimize_anything', disjoint):
        replayed = {phase: measure(panels, baseline, previous[phase], native[phase]) for phase, panels in data.items()}
    phases = {name: values for name, (values, _) in replayed.items()}
    prior = phases['prior-transfer']
    simple = affordable(SIMPLE, prior['totals'], prior['macroAccuracy'], prior['totals'][RETIRED]['paidLookups'])
    for name, (phase, subjects) in replayed.items():
        costs = phase['totals']
        ceiling = costs[RETIRED]['paidLookups']
        control = affordable(NATIVE, costs, phase['macroAccuracy'], ceiling)
        phase['simpleControlSelectedOnOriginalSubjects'] = compare(subjects, phase, simple, plan)
        phase['bestAffordableFixedNative'] = compare(subjects, phase, control, plan)
    return {'plan': plan, 'planSha256': digest(plan), 'phases': phases, 'newProviderRequests': 0}


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
        parser.error('Use the current seal and a fresh output path')
    report = execute(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
