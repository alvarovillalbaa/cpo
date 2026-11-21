"""Rerank already-evaluated nominees before the original single admission."""

import argparse
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_witness_tie_budget as paired_bands, witness_mmlu_gap as gap
from cpo._contract import digest


ROOT, REPLAY = gap.ROOT, gap.REPLAY
PARENT = 'docs/witness-mmlu-gap-results-v1.json'
PARENT_SHA256 = 'fee5bb37def5ea5443eda846ae0037d2522c94038c151819e418681ae287a899'
BASE = 'original'
RULES = (BASE, 'smoothed-pass-rate', 'paired-margin', 'case-adjusted')
PHASES = gap.paired.PHASES


@dataclass(frozen=True)
class Nomination:
    original: str | None
    paid_search: int
    grades: dict


class _BeforeAdmission(Exception):
    pass


def prepare():
    earlier, reference, data = gap.prepare()
    raw = (ROOT / PARENT).read_bytes()
    if sha256(raw).hexdigest() != PARENT_SHA256 or json.loads(raw)['planSha256'] != digest(earlier):
        raise ValueError('Use the published MMLU gap evidence')
    plan = {'protocol': 'witness-paid-nominee-ranking-v1', 'parentReportSha256': PARENT_SHA256,
            'parentPlanSha256': digest(earlier), 'sourceSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'fallbackValidationCap': earlier['fallbackValidationCap'], 'rules': RULES, 'pairedCaseDraws': reference['plan']['draws'],
            'resamplingSeed': reference['plan']['seed'],
            'scope': 'Freeze the search prefix and trigger. Score only already-paid grades before one independent proof.',
            'fit': 'Use BBH and LMentry admissions to choose for both MMLU cohorts. Use MMLU admissions to choose for '
                   'BBH and LMentry. Maximize promotions within original proof spend, then choose the cheapest rule.',
            'gate': 'On each cohort, the rule selected elsewhere must fit original realized total lookups and '
                    'have a positive paired subject-and-case lower endpoint against original CPO.'}
    return plan, reference, data


def search_to_nomination(matrix, held, start, layouts, active, policy, cap):
    original = gap.paired.replay.original
    qualify = REPLAY.qualify
    reads = {}

    def stop(incumbent, challenger, *args, **kwargs):
        if challenger != incumbent:
            raise _BeforeAdmission(challenger)
        return qualify(incumbent, challenger, *args, **kwargs)

    def witness(incumbent, layout, observe, limits):
        def record(prompt, case):
            passed = observe(prompt, case)
            reads[prompt, case] = passed
            return passed

        return original.witness(incumbent, layout, record, limits)

    with patch.object(REPLAY, 'qualify', stop):
        try:
            _, paid, _, returned, proof = original.play(matrix, held, start, layouts, active, policy, witness)
        except _BeforeAdmission as ready:
            return Nomination(ready.args[0], len(reads), reads)
        if returned != reads or paid != len(reads) or proof:
            raise ValueError('The witness prefix disagrees with its paid ledger')
        fallback = gap.paired.CachedLookaheadHalving(metric_limit=cap, paid=reads)
        try:
            gap.paired.replay.capped.transfer_trial(matrix, held, start, layouts, active, policy, fallback)
        except _BeforeAdmission as ready:
            return Nomination(ready.args[0], paid + fallback.evaluations, fallback.observations)
    return Nomination(None, paid + fallback.evaluations, fallback.observations)


def rank(nomination, incumbent, enrolled):
    if nomination.original is None:
        return dict.fromkeys(RULES)
    by_prompt, by_case = {}, {}
    for (prompt, case), passed in nomination.grades.items():
        by_prompt.setdefault(prompt, {})[case] = passed
        by_case.setdefault(case, Counter()).update(passes=passed, reads=1)
    if nomination.original not in by_prompt:
        raise ValueError('The original nominee must have a paid validation grade')
    candidates = tuple(dict.fromkeys((nomination.original, *(prompt for prompt in enrolled if prompt in by_prompt))))
    seed = by_prompt.get(incumbent, {})

    def statistics(prompt):
        scores = by_prompt[prompt]
        paired = scores.keys() & seed.keys()
        smoothed = Fraction(sum(scores.values()) + 1, len(scores) + 2)
        margin = Fraction(sum(scores[case] - seed[case] for case in paired), len(paired) + 2)
        adjusted = sum(Fraction(passed) - Fraction(by_case[case]['passes'] - passed + 1, by_case[case]['reads'] + 1)
                       for case, passed in scores.items()) / (len(scores) + 2)
        return smoothed, margin, adjusted

    values = {prompt: statistics(prompt) for prompt in candidates}
    return {BASE: nomination.original, **{rule: max(candidates, key=lambda prompt: values[prompt][index])
                                         for index, rule in enumerate(RULES[1:])}}


def evaluate_nominees(matrix, held, start, layouts, active, policy, nomination):
    roster = {prompt: index for index, layout in enumerate(layouts) for prompt in layout['alternatives']}
    choices = rank(nomination, start, roster)
    results = {None: (start, 0)}
    evaluation = lambda prompt, case: matrix[int(prompt)][case] == '1'
    for nominee in dict.fromkeys(choices.values()):
        if nominee is None:
            continue
        cycle = roster[nominee]
        layout = layouts[cycle]
        bank = [case for earlier in layouts[:cycle] for case in earlier['qualify']]
        if set(bank + layout['qualify']) & set(held):
            raise ValueError('An admission panel overlaps held-out cases')
        selected, _, receipt = REPLAY.qualify(start, nominee, layout['qualify'], bank, set(), evaluation,
                                              plan=active, seed=layout['seed'], recycle=policy == 'recycle-unread')
        proof = receipt['qualificationLookups']
        if not 0 < proof <= 2 * (len(layout['qualify']) + active['maximumExtensionRows']):
            raise ValueError('Nominee ranking exceeded the existing single-proof allowance')
        results[nominee] = selected, proof
    return {rule: (*results[prompt], prompt != nomination.original) for rule, prompt in choices.items()}


def measure(inputs, panels, _native, _conditions, cap, fallback_cap):
    schedule, policy = inputs['schedule'], inputs['qualificationBank']
    active = {**schedule, 'evaluationLookupLimit': cap}
    subjects, traces = {}, {}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        identity = tuple(panel['caseIDs'][i] for i in held) if 'caseIDs' in panel else panel['caseOrderSha256']
        group = subjects.setdefault(subject, {'identity': identity, 'held': held, 'decisionsPerCase': 0,
                                               'counts': {rule: Counter() for rule in RULES},
                                               'cases': {rule: [0] * len(held) for rule in RULES}})
        if (group['identity'], group['held']) != (identity, held):
            raise ValueError('Both recorded models must use the same physical cases')
        group['decisionsPerCase'] += len(schedule['seeds'])
        trace = []
        for seed in schedule['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
            nomination = search_to_nomination(matrix, held, start, layouts, active, policy, fallback_cap)
            outcomes = evaluate_nominees(matrix, held, start, layouts, active, policy, nomination)
            for rule, (selected, proof, switched) in outcomes.items():
                scores = [matrix[int(selected)][case] == '1' for case in held]
                group['cases'][rule] = [a + b for a, b in zip(group['cases'][rule], scores, strict=True)]
                group['counts'][rule].update(holdoutPasses=sum(scores), paidLookups=nomination.paid_search + proof,
                                              proofLookups=proof, promotions=int(selected != start),
                                              nominations=int(nomination.original is not None), changedNominees=int(switched))
            trace.append((seed, nomination.paid_search, nomination.original, outcomes))
        traces[f'{subject}/{model}'] = digest(trace)
    return subjects, traces


def proof_stats(groups):
    fields = ('proofLookups', 'promotions')
    return {rule: {field: sum(group['counts'][rule][field] for group in groups) for field in fields} for rule in RULES}


def fit(stats):
    eligible = [rule for rule in RULES if stats[rule]['proofLookups'] <= stats[BASE]['proofLookups']]
    return min(eligible, key=lambda rule: (-stats[rule]['promotions'], stats[rule]['proofLookups'], RULES.index(rule)))


def summarize(plan, groups, reference, selected):
    results = {}
    votes = {name: {'decisionsPerCase': unit['decisionsPerCase'], 'cases': unit['cases']} for name, unit in groups.items()}
    for rule in RULES:
        total = sum((unit['counts'][rule] for unit in groups.values()), Counter())
        macro = sum(Fraction(sum(unit['cases'][rule]), len(unit['held']) * unit['decisionsPerCase'])
                    for unit in groups.values()) / len(groups)
        with patch.object(paired_bands, 'BASELINE', BASE):
            band = paired_bands.paired_ranges(votes, rule, plan)
        native = {arm: row for arm, row in reference['totals'].items()
                  if (arm.startswith('gepa-') or arm == gap.paired.replay.START) and row['paidLookups'] <= total['paidLookups']}
        best = min(native, key=lambda arm: (-Fraction(native[arm]['macroAccuracy']), native[arm]['paidLookups'], arm))
        results[rule] = {**total, 'macroAccuracy': str(macro), 'pairedVsOriginal': band,
                         'affordableNativeOnObservedTotals': {'arm': best, **native[best]}}
    original = reference['totals'][gap.paired.replay.CANDIDATE]
    if any(results[BASE][key] != original[key] for key in ('holdoutPasses', 'paidLookups')):
        raise ValueError('The frozen original nomination path failed to reproduce')
    chosen = results[selected]
    passes = (chosen['paidLookups'] <= results[BASE]['paidLookups'] and
              chosen['pairedVsOriginal']['subjectsAndCases']['interval95PercentagePoints'][0] > 0)
    return {'methods': results, 'selectedOutsideFamily': selected, 'qualifies': passes}


def execute(plan, reference, data):
    groups, traces = {}, {}
    for name in PHASES:
        groups[name], traces[name] = measure(*data[name], plan['fallbackValidationCap'])
    bbh = proof_stats(list(groups[gap.paired.BBH].values()))
    mmlu = proof_stats([unit for name in gap.paired.replay.PHASES for unit in groups[name].values()])
    training = {'bbh-lmentry': {'stats': bbh, 'selected': fit(bbh)},
                'mmlu': {'stats': mmlu, 'selected': fit(mmlu)}}
    selected = {name: training['mmlu' if name == gap.paired.BBH else 'bbh-lmentry']['selected'] for name in PHASES}
    results = {name: {**summarize(plan, groups[name], reference['cohorts'][name], selected[name]),
                      'panelTraceSha256': traces[name]} for name in PHASES}
    return {'plan': plan, 'planSha256': digest(plan), 'newProviderRequests': 0, 'trainingAdmissionOnly': training,
            'cohorts': results, 'qualifies': all(row['qualifies'] for row in results.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', metavar='PLAN_SHA256')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, *inputs = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Replay requires the current seal and a fresh report path')
    report = execute(plan, *inputs)
    with args.out.open('x') as out:
        json.dump(report, out, indent=2, sort_keys=True)
        out.write('\n')


if __name__ == '__main__':
    main()
