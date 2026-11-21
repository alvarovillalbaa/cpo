"""Use an additional already-graded incumbent case before spending the only admission."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from random import Random
from unittest.mock import patch

from benchmarks import prompteval_matched_admission_attempt as matched
from benchmarks import prompteval_narrow_native_admission as narrow
from benchmarks import prompteval_witness_tie_budget as paired
from cpo._contract import digest


REPLAY = matched.REPLAY
BASELINE = matched.first(matched.CPO)
VETO = 'check-extra-witness'
RESCUE = 'check-and-retry-second-finalist'
METHODS = (BASELINE, VETO, RESCUE)
REFERENCE = matched.transfer.ROOT / 'docs/prompteval-narrow-native-admission-results-v1.json'
REFERENCE_SHA = '16e1dc37d6a088d2b4d6f1b3cb58e4153460490d10234ddb6c5c53fc49fd7092'


def guarded_nominee(incumbent, layout, observe, active, counts, *, rescue):
    """Check an extra incumbent grade only when it was part of the original search."""
    paid = {}

    def read(prompt, case):
        key = prompt, case
        if key not in paid:
            paid[key] = observe(prompt, case)
        return paid[key]

    nominee = matched.transfer.select(matched.CPO, incumbent, layout, read, active)
    if nominee == incumbent:
        return incumbent
    order = list(layout['validation'])
    Random(layout['seed']).shuffle(order)
    first_pass, first_miss = (next((case for case in order if paid.get((incumbent, case)) is grade), None)
                              for grade in (True, False))
    extra = next((case for case in reversed(order)
                  if case not in (first_pass, first_miss) and (incumbent, case) in paid), None)
    if extra is None:
        return nominee

    def check(prompt):
        key = prompt, extra
        if key not in paid:
            if len(paid) >= active['evaluationLookupLimit']:
                return None
            counts['extraLogicalLookups'] += 1
        return read(prompt, extra)

    confirmed = check(nominee)
    if confirmed is None:
        return nominee
    counts['checkedExtraWitnesses'] += 1
    counts['extraIncumbentMisses'] += paid[incumbent, extra] is False
    if confirmed:
        return nominee
    counts['vetoedNominees'] += 1
    if rescue:
        other = next((prompt for prompt in layout['alternatives']
                      if prompt != nominee and paid.get((prompt, first_miss)) is True
                      and (first_pass is None or paid.get((prompt, first_pass)) is True)), None)
        if other is not None and check(other):
            counts['rescuedNominees'] += 1
            return other
    return incumbent


def episode(matrix, held, start, layouts, active, method, policy):
    attempted = False
    activity = Counter()

    def search(_name, incumbent, layout, observe, limits):
        nonlocal attempted
        if attempted:
            return incumbent
        if method == BASELINE:
            selected = matched.transfer.select(matched.CPO, incumbent, layout, observe, limits)
        else:
            selected = guarded_nominee(incumbent, layout, observe, limits, activity, rescue=method == RESCUE)
        attempted = selected != incumbent
        return selected

    with patch.object(REPLAY, 'search', search):
        final, counts, trace = REPLAY.run_arm(matrix, held, start, layouts, active, matched.CPO, policy)
    counts.update(activity)
    counts['admissions'] = int(attempted)
    return final, counts, trace


def prepare():
    upstream, baseline, data, _ = matched.prepare()
    comparison = matched.transfer.ROOT / 'docs/prompteval-matched-admission-attempt-results-v1.json'
    raw = comparison.read_bytes()
    prior = json.loads(raw)
    if sha256(raw).hexdigest() != narrow.REFERENCE_SHA or prior['planSha256'] != digest(upstream):
        raise ValueError('The matched-admission replay differs from its sealed receipt')
    original, _, _, _ = narrow.prepare()
    raw = REFERENCE.read_bytes()
    native = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or native['planSha256'] != digest(original):
        raise ValueError('The narrower native replay differs from its sealed receipt')
    plan = {'protocol': 'prompteval-one-admission-witness-guard-v1', 'priorPlanSha256': digest(upstream),
            'matchedReceiptSha256': narrow.REFERENCE_SHA, 'narrowerReceiptSha256': REFERENCE_SHA,
            'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(), 'methods': METHODS, 'primary': VETO,
            'pairedCaseDraws': upstream['pairedCaseDraws'], 'resamplingSeed': upstream['resamplingSeed'],
            'scope': ('Use the original nomination and the last already-graded extra incumbent case in seeded order. '
                      'Require the nominee to pass it when an additional lookup fits. The secondary arm may '
                      'send the other original finalist to admission. Allow at most one admission attempt.')}
    return plan, baseline, data, prior['phases'], native['totals']


def measure(panels, baseline, plan, reference):
    subjects, receipts = {}, {}
    totals = {method: Counter() for method in METHODS}
    active = {**baseline['schedule'], 'evaluationLookupLimit': baseline['searchCaps'][matched.CPO]}
    for panel in panels:
        subject, model, matrix = (panel[key] for key in ('subject', 'model', 'correctness'))
        key = f'{subject}/{model}'
        held = REPLAY.transfer.holdout(subject, len(matrix[0]))
        physical = [panel['caseIDs'][case] for case in held] if 'caseIDs' in panel else held
        group = subjects.setdefault(subject, {'caseIds': physical, 'decisionsPerCase': 0,
                                              'cases': {method: [0] * len(held) for method in METHODS}})
        if physical != group['caseIds']:
            raise ValueError('A paired subject must use the same holdout case identities')
        group['decisionsPerCase'] += len(active['seeds'])
        counts, traces = {method: Counter() for method in METHODS}, {method: [] for method in METHODS}
        for seed in active['seeds']:
            start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, active)
            for method in METHODS:
                final, receipt, trace = episode(matrix, held, start, layouts, active, method, baseline['qualificationBank'])
                counts[method].update(receipt)
                traces[method].append((seed, final, trace))
                group['cases'][method] = [value + (matrix[int(final)][case] == '1')
                                          for value, case in zip(group['cases'][method], held, strict=True)]
        original = reference['panels'][key][BASELINE]
        if any(original[field] != counts[BASELINE][field] for field in ('holdoutPasses', 'paidLookups')):
            raise ValueError('The original one-admission baseline changed its score or cost')
        for arm in METHODS:
            totals[arm].update(counts[arm])
        receipts[key] = {method: {**counts[method], 'traceSha256': digest(traces[method])} for method in METHODS}
    levels = {name: sum(Fraction(sum(group['cases'][name]), len(group['caseIds']) * group['decisionsPerCase'])
                         for group in subjects.values()) / len(subjects) for name in METHODS}
    return {'totals': totals, 'macroAccuracy': {name: str(score) for name, score in levels.items()}, 'panels': receipts,
            'pairedVsOriginal': {method: paired.paired_ranges(
                {subject: {**panel, 'cases': {paired.BASELINE: panel['cases'][BASELINE], method: panel['cases'][method]}}
                 for subject, panel in subjects.items()}, method, plan) for method in METHODS[1:]}}


def execute(plan, baseline, data, prior, narrow_native):
    phases = {}
    for phase, panels in data.items():
        measured = measure(panels, baseline, plan, prior[phase])
        source = prior[phase]
        controls = {arm: {**values, 'macroAccuracy': source['macroAccuracy'][arm]}
                    for arm, values in source['totals'].items() if arm.startswith('gepa-') or arm == matched.START}
        if phase == 'bbh-lmentry-transfer':
            controls.update({arm: values for arm, values in narrow_native.items() if arm.startswith('gepa-')})
        levels = {arm: values['macroAccuracy'] for arm, values in controls.items()}
        measured['bestAffordableFixedNative'] = {
            arm: matched.prior.affordable(controls, controls, levels, measured['totals'][arm]['paidLookups'])
            for arm in METHODS}
        measured['nativeControls'] = controls
        phases[phase] = measured
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
        parser.error('Use the current plan seal and a fresh output path')
    result = execute(plan, *inputs)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')


if __name__ == '__main__':
    main()
