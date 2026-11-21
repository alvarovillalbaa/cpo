"""Test the 16-lookup witness fallback on the two recorded MMLU cohorts."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_narrow_native_admission as native
from benchmarks import prompteval_rotating_witness_case_evidence as paired
from benchmarks import prompteval_witness_fallback as original
from benchmarks import witness_fallback_caps as capped
from benchmarks.promptolution_witness_small_native import SMALL
from cpo._contract import digest
from cpo.halving import HalvingSearch


ROOT = original.ROOT
PHASES = ('prior-transfer', 'additional-subjects')
BASE, START = original.BASE, native.START
CANDIDATE = 'witness-then-halving/cap-16'
HALVING = {f'halving-only/{limit}': limit for limit in (6, 8, 12, 16, 24, 32)}
REFERENCE = 'docs/prompteval-matched-admission-attempt-results-v1.json'
REFERENCE_SHA = 'f0d3591f4d1eca35336ed1637a995894e44c2c5205eafa78b178ae306227efcf'
CAP_EVIDENCE = 'docs/witness-fallback-caps-results-v1.json'
CAP_SHA = '49732022e1f778ca5bdf28dee1fd51f48fe9457d5b49131328527d249c27ba5c'
REPLAY = original.REPLAY


def prepare():
    prior, baseline, data, _ = native.matched.prepare()
    reference = (ROOT / REFERENCE).read_bytes()
    receipt = json.loads(reference)
    if (sha256(reference).hexdigest() != REFERENCE_SHA or receipt['planSha256'] != digest(prior)
            or sha256((ROOT / CAP_EVIDENCE).read_bytes()).hexdigest() != CAP_SHA):
        raise ValueError('Use the published matched-admission and fallback cap receipts')
    stages = {name: data[name] for name in PHASES}
    cohorts = {name: sorted({panel['subject'] for panel in panels}) for name, panels in stages.items()}
    if set(cohorts[PHASES[0]]) & set(cohorts[PHASES[1]]) or [len(stages[name]) for name in PHASES] != [18, 8]:
        raise ValueError('Use both complete subject-disjoint MMLU cohorts')
    conditions = {**SMALL, **native.native_settings(),
                  **{arm: {'validationRows': baseline['schedule']['validationRows'],
                           'searchCap': prior['searchCaps'][arm.rsplit('/', 1)[0]]} for arm in native.WIDE}}
    paths = (Path(__file__).resolve(), Path(capped.__file__), Path(original.__file__), Path(native.__file__),
             Path(paired.__file__), ROOT / 'cpo/halving/__init__.py', ROOT / 'requirements-benchmark.txt')
    plan = {'protocol': 'prompteval-mmlu-witness-fallback-v1', 'parentPlanSha256': digest(prior),
            'parentReportSha256': REFERENCE_SHA, 'fallbackCapEvidenceSha256': CAP_SHA,
            'sourceSha256': {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in paths},
            'cohorts': cohorts, 'candidate': CANDIDATE, 'base': BASE, 'fallbackNewLookups': 16,
            'fallbackLogicalLimit': 8, 'baseSearchCap': prior['searchCaps'][native.matched.CPO],
            'nativeSettings': conditions, 'halvingOnlySettings': HALVING, 'draws': prior['pairedCaseDraws'],
            'seed': prior['resamplingSeed'], 'gepaVersion': baseline['gepaVersion'],
            'gate': ('On each cohort require a positive subject-and-case lower endpoint against the best '
                     'affordable fixed control, including the original witness and retention. Treat the '
                     'combined cohort and the hindsight allocation as diagnostic.')}
    return plan, baseline, stages, {name: receipt['phases'][name] for name in PHASES}


def selection(matrix, held, start, layouts, active, policy):
    prompt, paid, trace, grades, proof = original.play(matrix, held, start, layouts, active, policy, original.witness)
    counters = Counter()
    if proof:
        return (prompt, paid, trace), (prompt, paid, trace), counters
    search = HalvingSearch(metric_limit=16, paid=grades)
    challenger, extra_proof = capped.transfer_trial(matrix, held, start, layouts, active, policy, search)
    if search.exhausted and extra_proof:
        raise ValueError('A capped fallback attempted proof')
    counters.update(fallbacks=1, cappedEpisodes=int(search.exhausted), promotions=int(challenger != start),
                    validationLookups=search.evaluations, proofLookups=extra_proof)
    return (prompt, paid, trace), (challenger, paid + search.evaluations + extra_proof,
                                   digest((trace, list(search.observations.items()), extra_proof))), counters


def measure_panel(panel, plan, baseline, reference, subjects):
    subject, model, matrix, identity = (panel[key] for key in ('subject', 'model', 'correctness', 'caseOrderSha256'))
    key = f'{subject}/{model}'
    methods = (CANDIDATE, BASE, START, *HALVING, *plan['nativeSettings'])
    held = REPLAY.transfer.holdout(subject, len(matrix[0]))
    unit = subjects.setdefault(subject, {'caseIds': held, 'caseOrderSha256': identity, 'decisionsPerCase': 0,
                                         'cases': {arm: [0] * len(held) for arm in methods}, 'paidLookups': Counter()})
    if unit['caseIds'] != held or unit['caseOrderSha256'] != identity:
        raise ValueError('Both models must align to the same recorded case columns')
    schedule, policy = baseline['schedule'], baseline['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': plan['baseSearchCap']}
    unit['decisionsPerCase'] += len(schedule['seeds'])
    counts = {arm: Counter() for arm in methods}
    traces = {arm: [] for arm in methods}
    for seed in schedule['seeds']:
        start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
        fixed, fallback, extra = selection(matrix, held, start, layouts, active, policy)
        result = {BASE: fixed, CANDIDATE: fallback, START: (start, 0, None)}
        counts[CANDIDATE].update(extra)
        for arm, limit in HALVING.items():
            def halving(incumbent, layout, observe, _envelope):
                search = HalvingSearch(metric_limit=limit)
                winner = search.select((incumbent, *layout['alternatives']), layout['validation'], observe,
                                       logical_limit=limit)
                if winner is None:
                    raise ValueError('The nominal Halving schedule exceeded its logical allowance')
                return winner

            result[arm] = original.play(matrix, held, start, layouts, active, policy, halving)[:3]
        for arm, condition in plan['nativeSettings'].items():
            own = {**schedule, 'evaluationLookupLimit': condition['searchCap']}
            prompt, costs, trace = native.capped_episode(matrix, held, start, layouts, own, arm, policy,
                                                         condition['validationRows'])
            result[arm] = prompt, costs['paidLookups'], trace
        for arm, (prompt, spent, trace) in result.items():
            decisions = [matrix[int(prompt)][case] == '1' for case in held]
            counts[arm].update(holdoutPasses=sum(decisions), paidLookups=spent)
            unit['paidLookups'][arm] += spent
            unit['cases'][arm] = [old + new for old, new in zip(unit['cases'][arm], decisions, strict=True)]
            traces[arm].append((seed, prompt, trace))
    for arm in (BASE, START, *native.WIDE):
        if any(counts[arm][metric] != reference[key][arm][metric] for metric in ('holdoutPasses', 'paidLookups')):
            raise ValueError('A published MMLU arm changed its paid cost or accuracy')
    return key, {arm: {**values, 'traceSha256': digest(traces[arm])} for arm, values in counts.items()}


def summarize(plan, subjects):
    table = {}
    arms = (CANDIDATE, BASE, START, *HALVING, *plan['nativeSettings'])
    for arm in arms:
        votes = [sum(item['cases'][arm]) for item in subjects.values()]
        sizes = [len(item['caseIds']) * item['decisionsPerCase'] for item in subjects.values()]
        accuracy = sum(Fraction(count, size) for count, size in zip(votes, sizes, strict=True)) / len(sizes)
        table[arm] = {'holdoutPasses': sum(votes), 'macroAccuracy': str(accuracy),
                      'paidLookups': sum(item['paidLookups'][arm] for item in subjects.values())}
    lookup_budget = table[CANDIDATE]['paidLookups']
    comparisons = {}
    for key, controls in (('native', (START, *plan['nativeSettings'])), ('allControls', arms[1:])):
        eligible = [arm for arm in controls if table[arm]['paidLookups'] <= lookup_budget]
        fixed = min(eligible, key=lambda arm: (-Fraction(table[arm]['macroAccuracy']), table[arm]['paidLookups'], arm))
        with patch.multiple(paired, CANDIDATE=CANDIDATE, NATIVE=controls, POINTS=(CANDIDATE, *controls)):
            bands = {axis: paired.resample(subjects, plan, resample_subjects=draw) for axis, draw in (
                ('fixedSubjects', False), ('subjectsAndCases', True))}
            allocation = paired.native_allocation(subjects, lookup_budget)
        comparisons[key] = {'strongestAffordableFixed': fixed, 'pairedAgainstReselectedFixed': {
            axis: values['comparisons']['best-affordable-gepa'] for axis, values in bands.items()},
            'controlSelections': {axis: values['affordableSelections'] for axis, values in bands.items()},
            'hindsightSubjectAllocation': allocation,
            'pairedAgainstOriginalWitness': {axis: values['comparisons'][BASE] for axis, values in bands.items()}
            if BASE in controls else None}
    return {'totals': table, 'comparisons': comparisons, 'subjects': len(subjects),
            'distinctHoldoutCases': sum(len(group['caseIds']) for group in subjects.values())}


def execute(plan, baseline, data, reference):
    if version('gepa') != plan['gepaVersion']:
        raise ValueError('Use hash-pinned GEPA 0.1.4')
    optimizer = import_module('gepa.optimize_anything')
    run = optimizer.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        train, hold = [native.transfer.CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if train.by_id.keys() & hold.by_id.keys():
            raise ValueError('Native GEPA train and validation IDs overlap')
        return run(*args, dataset=train, valset=hold, **settings)

    outputs, pooled = {}, {}
    with patch.object(optimizer, 'optimize_anything', disjoint):
        for phase, panels in data.items():
            groups = {}
            detail = dict(measure_panel(panel, plan, baseline, reference[phase]['panels'], groups) for panel in panels)
            pooled.update(groups)
            outputs[phase] = {**summarize(plan, groups), 'panels': detail}
    qualifies = all(row['comparisons']['allControls']['pairedAgainstReselectedFixed']['subjectsAndCases']
                    ['interval95PercentagePoints'][0] > 0 for row in outputs.values())
    return {'plan': plan, 'planSha256': digest(plan), 'qualifies': qualifies, 'phases': outputs,
            'pooled': summarize(plan, pooled), 'newProviderRequests': 0}


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
        parser.error('Replay requires the current seal and a fresh report path')
    result = execute(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, sort_keys=True, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
