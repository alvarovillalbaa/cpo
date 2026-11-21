"""Match CPO against GEPA using fewer validation anchors and one admission."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
from importlib import import_module
from importlib.metadata import version
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks import prompteval_matched_admission_attempt as matched
from benchmarks import prompteval_rotating_witness_case_evidence as audit
from benchmarks import prompteval_rotating_witness_transfer as transfer
from cpo._contract import digest


REPLAY = transfer.replay
CPO = matched.first(matched.CPO)
START = matched.START
WIDE = (matched.first(matched.NATIVE[0]), matched.first(matched.NATIVE[2]))
REFERENCE = transfer.ROOT / 'docs/prompteval-matched-admission-attempt-results-v1.json'
REFERENCE_SHA = 'f0d3591f4d1eca35336ed1637a995894e44c2c5205eafa78b178ae306227efcf'


def native_settings():
    settings = {}
    probes = REPLAY.transfer.PROBES
    for rows in (8, 12, 16):
        reserve = rows + 2 * probes
        for shape, multiplier in (('sequential', 1), ('sequential', 2), ('batched', 2)):
            cap = rows + multiplier * reserve
            arm = f'gepa-{shape}/validation-{rows}/cap-{cap}/one-admission'
            settings[arm] = {'validationRows': rows, 'searchCap': cap}
    return settings


def capped_episode(matrix, held, initial, layouts, active, method, policy, width):
    """Run one admission directly, using a fixed prefix of the original anchors."""
    attempted = False

    def search(name, incumbent, layout, observe, limits):
        nonlocal attempted
        if attempted:
            return incumbent
        validation = layout['validation'][:width]
        if len(validation) != width:
            raise ValueError('The selected width exceeds the frozen anchor panel')
        selected = transfer.select(name, incumbent, {**layout, 'validation': validation}, observe, limits)
        attempted = selected != incumbent
        return selected

    with patch.object(REPLAY, 'search', search):
        return REPLAY.run_arm(matrix, held, initial, layouts, active, method, policy)


def prepare():
    upstream, baseline, data, _ = matched.prepare()
    raw = REFERENCE.read_bytes()
    previous = json.loads(raw)
    if sha256(raw).hexdigest() != REFERENCE_SHA or previous['planSha256'] != digest(upstream):
        raise ValueError('Use the original matched-admission replay inputs and receipt')
    schedule = baseline['schedule']
    width = schedule['validationRows']
    settings = {CPO: {'validationRows': width, 'searchCap': upstream['searchCaps'][matched.CPO]},
                **{arm: {'validationRows': width, 'searchCap': upstream['searchCaps'][arm.rsplit('/', 1)[0]]}
                   for arm in WIDE}, **native_settings()}
    plan = {'protocol': 'prompteval-narrow-native-admission-v1', 'parentPlanSha256': digest(upstream),
            'parentReceiptSha256': REFERENCE_SHA, 'runnerSha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'conditions': settings, 'scope': 'All 44 BBH and LMentry panels with one admission per episode.',
            'selection': 'Use the first enrolled anchors within each episode. Select the best affordable '
                         'fixed native point again in each paired bootstrap draw.',
            'draws': upstream['pairedCaseDraws'], 'seed': upstream['resamplingSeed']}
    return plan, baseline, data['bbh-lmentry-transfer'], previous['phases']['bbh-lmentry-transfer']


def measure_panel(panel, baseline, plan, expected, subjects):
    arms = (START, *plan['conditions'])
    subject, model, matrix = (panel[name] for name in ('subject', 'model', 'correctness'))
    key = f'{subject}/{model}'
    held = REPLAY.transfer.holdout(subject, len(matrix[0]))
    physical = [panel['caseIDs'][case] for case in held]
    group = subjects.setdefault(subject, {'caseIds': physical, 'decisionsPerCase': 0,
                                          'cases': {arm: [0] * len(held) for arm in arms}, 'paidLookups': Counter()})
    if len(set(physical)) != len(held) or physical != group['caseIds']:
        raise ValueError('The models must share the same case identities on holdout')
    schedule = baseline['schedule']
    group['decisionsPerCase'] += len(schedule['seeds'])
    counts = {arm: Counter() for arm in arms}
    traces = {arm: [] for arm in plan['conditions']}
    for seed in schedule['seeds']:
        start, layouts = REPLAY.schedule(len(matrix[0]), len(matrix), held, seed, schedule)
        outcomes = {START: (start, 0)}
        for arm, condition in plan['conditions'].items():
            active = {**schedule, 'evaluationLookupLimit': condition['searchCap']}
            method = matched.CPO if arm == CPO else arm
            selected, costs, trace = capped_episode(matrix, held, start, layouts, active, method,
                                                    baseline['qualificationBank'], condition['validationRows'])
            outcomes[arm] = selected, costs['paidLookups']
            counts[arm]['searchLookups'] += costs['searchLookups']
            counts[arm]['qualificationLookups'] += costs['qualificationLookups']
            traces[arm].append((seed, selected, trace))
        for arm, (selected, paid) in outcomes.items():
            outcomes_on_cases = [matrix[int(selected)][case] == '1' for case in held]
            counts[arm].update(holdoutPasses=sum(outcomes_on_cases), paidLookups=paid)
            group['paidLookups'][arm] += paid
            group['cases'][arm] = [a + b for a, b in zip(group['cases'][arm], outcomes_on_cases, strict=True)]
    for arm in (START, CPO, *WIDE):
        source = expected['panels'][key][arm]
        if any(counts[arm][field] != source[field] for field in ('holdoutPasses', 'paidLookups')):
            raise ValueError('A sealed one-admission control changed its score or cost')
    return key, {arm: {**counts[arm], **({'traceSha256': digest(traces[arm])} if arm in traces else {})} for arm in arms}


def execute(plan, baseline, data, expected):
    if version('gepa') != baseline['gepaVersion']:
        raise ValueError('Use pinned GEPA 0.1.4')
    module = import_module('gepa.optimize_anything')
    original = module.optimize_anything

    def disjoint(*args, dataset, valset, **settings):
        train, validation = [transfer.CaseRows({**row, 'id': row['case']} for row in rows) for rows in (dataset, valset)]
        if train.by_id.keys() & validation.by_id.keys():
            raise ValueError('GEPA train and validation IDs overlap')
        return original(*args, dataset=train, valset=validation, **settings)

    subjects = {}
    with patch.object(module, 'optimize_anything', disjoint):
        panels = dict(measure_panel(panel, baseline, plan, expected, subjects) for panel in data)
    native = (START, *(arm for arm in plan['conditions'] if arm != CPO))
    arms = (CPO, *native)
    accuracy = {arm: sum(Fraction(sum(group['cases'][arm]), len(group['caseIds']) * group['decisionsPerCase'])
                         for group in subjects.values()) / len(subjects) for arm in arms}
    paid = sum((group['paidLookups'] for group in subjects.values()), Counter())
    with patch.multiple(audit, CANDIDATE=CPO, NATIVE=native, POINTS=arms):
        control = audit.affordable(accuracy, paid)
        ranges = {axis: audit.resample(subjects, plan, resample_subjects=resample_subjects)
                  for axis, resample_subjects in (('casesWithinFixedSubjects', False), ('subjectsAndCases', True))}
    totals = {arm: {'paidLookups': paid[arm], 'holdoutPasses': sum(sum(g['cases'][arm]) for g in subjects.values()),
                    'macroAccuracy': str(accuracy[arm])} for arm in arms}
    return {'plan': plan, 'planSha256': digest(plan), 'totals': totals, 'panels': panels,
            'bestAffordableNative': control, 'pairedResampling': ranges,
            'distinctHoldoutCases': sum(len(g['caseIds']) for g in subjects.values()), 'newProviderRequests': 0}


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
