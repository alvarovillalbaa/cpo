"""Use paid admission outcomes as witnesses only after their cases retire."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_rotating_witness_transfer as transfer
from benchmarks import prompteval_witness_tie_budget as previous
from cpo._contract import digest


REPLAY = transfer.replay
BASELINE = transfer.CANDIDATE
ANCHORS = 'paid-validation-witnesses'
RETIRED = 'retired-admission-witnesses'
METHODS = (BASELINE, ANCHORS, RETIRED)
REFERENCE = transfer.ROOT / 'docs/prompteval-witness-tie-budget-results-v1.json'
REFERENCE_SHA = '68b9055a4d3fc42bbfaa9a3e27cf9cabaca863c5fbc720d2e86448d050f92578'


def witnesses(incumbent, layout, search_cache, retired_grades):
    """Prefer previously paid grades and keep seeded anchors for finalist scoring."""
    anchors = list(layout['validation'])
    Random(layout['seed']).shuffle(anchors)
    retired = sorted(case for prompt, case in retired_grades if prompt == incumbent)
    Random(layout['seed']).shuffle(retired)
    seen = {**search_cache, **retired_grades}
    pair = tuple(next((case for case in (*retired, *anchors) if seen.get((incumbent, case)) is grade), None)
                 for grade in (True, False))
    if None in pair:
        return anchors, set(), False
    moved = set(pair).intersection(retired)
    return [*pair, *(case for case in anchors if case not in pair)], moved, True


def history_episode(matrix, holdout, initial, layouts, active, method):
    bank, touched, search_cache, retired, trace = [], set(), {}, {}, []
    totals = Counter()
    reserved = {case for layout in layouts for case in layout['qualify']}
    excluded = reserved.union(holdout)
    if len(reserved) != sum(len(layout['qualify']) for layout in layouts) or reserved.intersection(holdout):
        raise ValueError('Admission and holdout must use disjoint cases')
    incumbent = initial

    def score(prompt, case):
        return matrix[int(prompt)][case] == '1'

    for layout in layouts:
        train, anchors, current = (layout[name] for name in ('train', 'validation', 'qualify'))
        if set(train).intersection(anchors) or excluded.intersection((*train, *anchors)):
            raise ValueError('The original search schedule overlaps a protected split')
        eligible = retired if method == RETIRED else {}
        order, moved, cached = witnesses(incumbent, layout, search_cache, eligible)
        if not moved <= touched or moved.intersection(current) or moved.intersection(bank):
            raise ValueError('Only previously observed and retired admission cases may enter later search')
        allowed = set(anchors).union(moved)
        prompts = {incumbent, *layout['alternatives']}
        logical = {}
        paid = Counter()

        def observe(prompt, case):
            if prompt not in prompts or case not in allowed:
                raise ValueError('A search used a case or prompt outside its validation scope')
            key = prompt, case
            if key not in logical:
                if len(logical) >= active['evaluationLookupLimit']:
                    raise ValueError('An arm exceeded the original logical search ceiling')
                if key not in search_cache:
                    if key in eligible:
                        search_cache[key] = eligible[key]
                        paid['reusedAdmissionGrades'] += 1
                    else:
                        search_cache[key] = score(prompt, case)
                        paid['newSearchLookups'] += 1
                        paid['newSearchLookupsOnRetiredCases'] += case in moved
                logical[key] = search_cache[key]
            return logical[key]

        challenger = transfer.discovery.witness_challenger(
            incumbent, {**layout, 'validation': order}, observe, active, finalists=2,
        )
        reserve = bank[:active['maximumExtensionRows']]
        selected, evidence, receipt = REPLAY.qualify(incumbent, challenger, current, bank, touched, score,
                                                     plan=active, seed=layout['seed'], recycle=False)
        audited, full, extended = REPLAY.audit_decision(incumbent, challenger, current, reserve, score,
                                                        threshold=active['minimumQualificationGain'], seed=layout['seed'])
        if selected != audited or evidence != full[:len(evidence)] or receipt['reserveAllocations'] != int(extended):
            raise ValueError('The admission result differs from its exact disjoint reference')
        for prompt, case, passed in evidence:
            key = prompt, case
            if case not in touched or key in search_cache or key in retired:
                raise ValueError('Admission attempted to reuse a search or retired observation')
            retired[key] = passed
        receipt['nominations'] = int(challenger != incumbent)
        incumbent = selected
        receipt.update(searchLookups=len(logical), reusedSearchLookups=len(logical) - paid['newSearchLookups'],
                       cachedWitnessCycles=int(cached), retiredWitnessCycles=int(bool(moved)), **paid)
        totals.update({key: value for key, value in receipt.items() if type(value) is int})
        trace.append((digest(list(logical.items())), challenger, incumbent, receipt, tuple(bank)))
    totals['paidLookups'] = totals['newSearchLookups'] + totals['qualificationLookups']
    totals['holdoutPasses'] = sum(score(incumbent, case) for case in holdout)
    if (len(retired) != totals['qualificationLookups'] or
            len(search_cache) != totals['newSearchLookups'] + totals['reusedAdmissionGrades']):
        raise ValueError('The ledgers do not reconcile with their paid and previously paid grades')
    return incumbent, totals, digest(trace)


def prepare():
    source, baseline, data, _ = previous.prepare()
    raw = REFERENCE.read_bytes()
    expected = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or expected['planSha256'] != digest(source):
        raise ValueError('Use the pinned previous rotating-witness inputs and controls')
    plan = {'protocol': 'prompteval-retired-admission-witness-v1', 'parentPlanSha256': digest(source),
            'parentReportSha256': REFERENCE_SHA, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'methods': METHODS, 'primary': RETIRED, 'pairedCaseDraws': source['pairedCaseDraws'],
            'resamplingSeed': source['resamplingSeed'], 'qualificationPolicy': baseline['qualificationBank'],
            'scope': ('Reuse incumbent witnesses available before this cycle. The admission arm also considers only '
                      'cases already read during an earlier independent admission. Anchor cases supply the finalist '
                      'tie-break. Keep the same logical cap, fixed holdout, and fresh paired admission.')}
    return plan, baseline, data, expected['phases']


def measure(panels, baseline, plan, expected):
    subjects, records = {}, {}
    totals = {method: Counter() for method in METHODS}
    active = {**baseline['schedule'], 'evaluationLookupLimit': baseline['searchCaps'][BASELINE]}
    for panel in panels:
        subject, model, matrix = (panel[name] for name in ('subject', 'model', 'correctness'))
        key = f'{subject}/{model}'
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        group = subjects.setdefault(subject, {'caseIds': held, 'decisionsPerCase': 0,
                                             'cases': {arm: [0] * len(held) for arm in METHODS}})
        if held != group['caseIds']:
            raise ValueError('The repeated physical holdout cohort changed across models')
        group['decisionsPerCase'] += len(active['seeds'])
        counts, traces = {arm: Counter() for arm in METHODS}, {arm: [] for arm in METHODS}
        for seed in active['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, active)
            nominations = 0

            def original_search(method, incumbent, layout, observe, plan):
                nonlocal nominations
                challenger = transfer.select(method, incumbent, layout, observe, plan)
                nominations += challenger != incumbent
                return challenger

            with patch.object(REPLAY, 'search', original_search):
                original = REPLAY.run_arm(matrix, held, start, layouts, active, BASELINE, baseline['qualificationBank'])
            outcomes = {BASELINE: original}
            outcomes.update({arm: history_episode(matrix, held, start, layouts, active, arm) for arm in METHODS[1:]})
            for arm, (final, receipt, trace) in outcomes.items():
                counts[arm].update(receipt)
                traces[arm].append((seed, final, trace))
                group['cases'][arm] = [before + (matrix[int(final)][case] == '1')
                                        for before, case in zip(group['cases'][arm], held, strict=True)]
            counts[BASELINE]['nominations'] += nominations
        records[key] = {arm: {**counts[arm], 'traceSha256': digest(traces[arm])} for arm in METHODS}
        original_record = {name: value for name, value in records[key][BASELINE].items() if name != 'nominations'}
        if original_record != expected['panels'][key][BASELINE]:
            raise ValueError('The original rotating-witness control changed')
        for arm, value in counts.items():
            totals[arm].update(value)
    macros = {arm: str(sum(Fraction(sum(group['cases'][arm]), len(group['caseIds']) * group['decisionsPerCase'])
                           for group in subjects.values()) / len(subjects)) for arm in METHODS}
    native_accuracy = {arm: expected['macroAccuracy'][arm] for arm in previous.CONTROLS}
    native_totals = {arm: expected['totals'][arm] for arm in previous.CONTROLS}
    return {'totals': totals, 'macroAccuracy': macros, 'panels': records,
            'nativeControlTotals': native_totals, 'nativeControlMacroAccuracy': native_accuracy,
            'distinctHoldoutCases': sum(len(group['caseIds']) for group in subjects.values()),
            'pairedRangesVsOriginalWitness': {arm: previous.paired_ranges(subjects, arm, plan) for arm in METHODS[1:]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    plan, baseline, data, references = prepare()
    seal = digest(plan)
    if args.execute is None and args.out is None:
        print(json.dumps({**plan, 'planSha256': seal}, indent=2, sort_keys=True))
        return
    if args.execute != seal or args.out is None or args.out.exists():
        parser.error('Use the current design seal and a fresh output path')
    results = {phase: measure(panels, baseline, plan, references[phase]) for phase, panels in data.items()}
    with args.out.open('x') as output:
        json.dump({'plan': plan, 'planSha256': seal, 'phases': results, 'newProviderRequests': 0},
                  output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
